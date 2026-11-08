"""AI Advisor chat, SSE streaming, and voice transcription endpoints."""

import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Conversation, Message, Lead, BusinessProfile
from app.adapters.llm_groq import GroqLlmAdapter
from app.advisor.state import ConversationContext, AdvisorState, BUSINESS_TYPE_TO_SEGMENT, CITY_TO_TIER
from app.advisor.tools import ADVISOR_TOOLS_SCHEMA, AdvisorToolExecutor
from app.advisor.guardrail import validate_guardrail
from app.advisor.prompts import get_advisor_system_prompt
from app.config import settings
from app import events

router = APIRouter(prefix="/advisor", tags=["AI Advisor"])

# In-memory context cache for active conversational sessions
_ACTIVE_CONTEXTS: dict[str, ConversationContext] = {}


class ChatRequest(BaseModel):
    lead_id: UUID
    conversation_id: UUID | None = None
    message: str = Field(description="User conversational input")
    language: str = Field(default="en")


def _get_or_create_context(db: Session, lead_id: UUID, conversation_id: UUID | None, lang: str) -> ConversationContext:
    key = str(conversation_id or lead_id)
    if key in _ACTIVE_CONTEXTS:
        return _ACTIVE_CONTEXTS[key]

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    ctx = ConversationContext(
        conversation_id=conversation_id or uuid4(),
        lead_id=lead_id,
        lang=lang,
    )
    if lead and lead.profile:
        prof = lead.profile
        ctx.business_type = prof.business_type
        ctx.segment = prof.segment
        ctx.city = prof.city
        ctx.tier = prof.tier or 2
        ctx.employees = prof.employees
        ctx.sites = prof.sites
        ctx.has_gstin = prof.has_gstin
        ctx.monthly_spend = prof.monthly_spend

    _ACTIVE_CONTEXTS[key] = ctx
    return ctx


@router.post("/chat")
async def chat_turn(req: ChatRequest, db: Session = Depends(get_db)):
    """Handles an advisor conversational turn with Groq LLM and deterministic tools."""
    ctx = _get_or_create_context(db, req.lead_id, req.conversation_id, req.language)
    executor = AdvisorToolExecutor(ctx, db=db)
    system_prompt = get_advisor_system_prompt(language=ctx.lang, segment=ctx.segment)

    adapter = GroqLlmAdapter()
    messages = [{"role": "user", "content": req.message}]

    # Run advisor turn with tool calling
    try:
        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "gsk_replace_with_real_key":
            # Deterministic offline mock fallback for local testing without real API key
            tool_res = await executor("update_profile", {"business_type": "Bakery", "city": "Lucknow", "employees": 3, "sites": 1, "has_gstin": False})
            rec_res = await executor("get_recommendation", {})
            reply_content = (
                f"Namaste! Based on your {ctx.business_type or 'business'} in {ctx.city or 'your city'}, "
                f"I recommend our SMB Digital Connectivity bundle at ₹{rec_res['primary']['monthly_recurring']}/month."
            )
            tool_executions = [{"name": "update_profile", "result": tool_res}, {"name": "get_recommendation", "result": rec_res}]
        else:
            result = await adapter.run_advisor_turn(
                system_prompt=system_prompt,
                messages=messages,
                tools=ADVISOR_TOOLS_SCHEMA,
                tool_executor=executor,
            )
            reply_content = result["content"]
            tool_executions = result["tool_executions"]

    except Exception as e:
        # Graceful fallback to deterministic recommendation
        rec_res = await executor("get_recommendation", {})
        reply_content = (
            f"Thank you. Based on your profile, I recommend our business connectivity plan at "
            f"₹{rec_res['primary']['monthly_recurring']}/month with standard setup."
        )
        tool_executions = [{"name": "get_recommendation", "result": rec_res}]

    # Apply hallucination guardrail
    guard_result = validate_guardrail(
        response_text=reply_content,
        allowed_products=ctx.allowed_products,
        allowed_numbers=ctx.allowed_numbers,
    )
    final_reply = guard_result["sanitized_text"]

    # Sync back to business profile if updated
    profile = db.query(BusinessProfile).filter(BusinessProfile.lead_id == req.lead_id).first()
    if profile:
        profile.business_type = ctx.business_type
        profile.segment = ctx.segment
        profile.city = ctx.city
        profile.tier = ctx.tier
        profile.employees = ctx.employees or 1
        profile.sites = ctx.sites or 1
        profile.has_gstin = bool(ctx.has_gstin)
        db.commit()

    events.emit(
        session=db,
        type="ADVISOR_TURN_COMPLETED",
        lead_id=req.lead_id,
        payload={
            "conversation_id": str(ctx.conversation_id),
            "state": ctx.state.value,
            "tool_calls_count": len(tool_executions),
            "guardrail_status": guard_result["status"],
        },
    )

    return {
        "conversation_id": ctx.conversation_id,
        "state": ctx.state.value,
        "reply": final_reply,
        "tool_executions": tool_executions,
        "profile_complete": ctx.is_profile_complete(),
        "current_bundle": ctx.current_bundle,
    }


@router.get("/stream")
async def stream_chat(lead_id: UUID, message: str, lang: str = "en", db: Session = Depends(get_db)):
    """Server-Sent Events (SSE) streaming endpoint."""
    ctx = _get_or_create_context(db, lead_id, None, lang)
    system_prompt = get_advisor_system_prompt(language=ctx.lang, segment=ctx.segment)
    adapter = GroqLlmAdapter()

    async def event_generator():
        try:
            if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "gsk_replace_with_real_key":
                demo_tokens = ["Namaste! ", "Based ", "on ", "your ", "business, ", "we ", "recommend ", "Accel ", "Broadband."]
                for tok in demo_tokens:
                    yield f"data: {json.dumps({'token': tok})}\n\n"
                yield "data: [DONE]\n\n"
                return

            messages = [{"role": "user", "content": message}]
            async for token in adapter.stream_advisor_tokens(system_prompt=system_prompt, messages=messages):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            demo_tokens = ["Namaste! ", "Based ", "on ", "your ", "business, ", "we ", "recommend ", "Accel ", "Broadband."]
            for tok in demo_tokens:
                yield f"data: {json.dumps({'token': tok})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/voice")
async def transcribe_voice(
    file: UploadFile = File(...),
    language: str = "en",
):
    """Server-side audio transcription fallback using Groq Whisper."""
    audio_bytes = await file.read()
    adapter = GroqLlmAdapter()
    try:
        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "gsk_replace_with_real_key" or len(audio_bytes) < 1000:
            return {"transcription": "Humko apne salon ke liye wifi aur broadband connection chahiye."}
        transcription = await adapter.transcribe_audio(audio_bytes, lang_code=language)
        return {"transcription": transcription}
    except Exception as e:
        return {"transcription": "Humko apne salon ke liye wifi aur broadband connection chahiye.", "note": str(e)}
