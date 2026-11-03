import json
from collections.abc import AsyncIterator
from typing import Any
from groq import AsyncGroq, BadRequestError
from app.config import settings
from app.ports import LlmPort


class GroqLlmAdapter:
    """Production Groq AI adapter implementing LlmPort for fast multilingual tool calling and inference."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.client = AsyncGroq(
            api_key=self.api_key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )

    async def run_advisor_turn(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_iterations: int = 4,
    ) -> dict[str, Any]:
        """Runs multi-turn tool calling with Groq Llama 3.3 70B."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        tool_executions_log = []

        for iteration in range(max_iterations):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.ADVISOR_MODEL,
                    messages=full_messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=0.2,
                )
            except BadRequestError as e:
                if "tool_use_failed" in str(e):
                    # Retry once deterministically at temperature=0.0
                    response = await self.client.chat.completions.create(
                        model=settings.ADVISOR_MODEL,
                        messages=full_messages,
                        tools=tools if tools else None,
                        tool_choice="auto" if tools else None,
                        temperature=0.0,
                    )
                else:
                    raise

            msg = response.choices[0].message

            # If tool calls are requested by LLM
            if msg.tool_calls:
                full_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}

                    # Execute tool via provided tool_executor
                    tool_result = await tool_executor(fn_name, args)
                    tool_executions_log.append({
                        "name": fn_name,
                        "args": args,
                        "result": tool_result,
                    })

                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    })
            else:
                # No more tool calls; final assistant response
                return {
                    "content": msg.content or "",
                    "tool_executions": tool_executions_log,
                    "model": settings.ADVISOR_MODEL,
                }

        # If max iterations reached, return whatever the last content is
        return {
            "content": msg.content or "",
            "tool_executions": tool_executions_log,
            "model": settings.ADVISOR_MODEL,
        }

    async def stream_advisor_tokens(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """SSE Token streaming support for instant responses."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = await self.client.chat.completions.create(
            model=settings.ADVISOR_MODEL,
            messages=full_messages,
            stream=True,
            temperature=0.2,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def extract_kyc_fields_vision(
        self, image_bytes: bytes, slot: str
    ) -> dict[str, Any]:
        """Vision-based fallback field extraction using Llama 4 Scout."""
        import base64
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            f"You are a KYC document extractor for Indian SME documents. "
            f"The document slot is '{slot}'. Extract key identification fields into JSON with confidence scores."
        )
        response = await self.client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_img}"},
                        },
                    ],
                }
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw_json = response.choices[0].message.content or "{}"
        try:
            return json.loads(raw_json)
        except Exception:
            return {"raw": raw_json}

    async def transcribe_audio(self, audio_bytes: bytes, lang_code: str = "en") -> str:
        """Speech-to-text fallback using Whisper large v3 turbo."""
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        transcription = await self.client.audio.transcriptions.create(
            file=audio_file,
            model=settings.STT_MODEL,
            language=lang_code,
            response_format="text",
        )
        return str(transcription).strip()
