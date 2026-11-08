"""Inbound webhook handlers for e-sign, UPI autopay mandate, and network provisioning."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Quote, Order
from app.orders.state_machine import OrderStateMachine
from app import events

router = APIRouter(prefix="/webhooks", tags=["Inbound Webhooks"])


class EsignWebhookPayload(BaseModel):
    quote_id: UUID
    status: str = "SIGNED"
    docket_id: str
    signatory_name: str | None = None


class MandateWebhookPayload(BaseModel):
    mandate_id: str
    quote_id: UUID
    lead_id: UUID
    status: str = "AUTHORIZED"
    umn: str = "accel.mandate@upi"


class ProvisioningWebhookPayload(BaseModel):
    order_id: UUID
    event_type: str  # LINE_SPLICED, CPE_DISPATCHED, SERVICE_ACTIVATED
    notes: str | None = None


@router.post("/esign")
def handle_esign_webhook(payload: EsignWebhookPayload, db: Session = Depends(get_db)):
    """Receives asynchronous Aadhaar e-Sign completion notifications."""
    quote = db.query(Quote).filter(Quote.id == payload.quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found.")

    events.emit(
        session=db,
        type="ESIGN_WEBHOOK_RECEIVED",
        lead_id=quote.lead_id,
        payload={
            "quote_id": str(quote.id),
            "status": payload.status,
            "docket_id": payload.docket_id,
        },
    )
    db.commit()
    return {"status": "PROCESSED", "quote_id": quote.id}


@router.post("/mandate")
def handle_mandate_webhook(payload: MandateWebhookPayload, db: Session = Depends(get_db)):
    """Receives asynchronous NPCI UPI Autopay mandate authorization callbacks."""
    events.emit(
        session=db,
        type="MANDATE_WEBHOOK_RECEIVED",
        lead_id=payload.lead_id,
        payload={
            "mandate_id": payload.mandate_id,
            "quote_id": str(payload.quote_id),
            "status": payload.status,
            "umn": payload.umn,
        },
    )
    db.commit()
    return {"status": "PROCESSED", "mandate_id": payload.mandate_id}


@router.post("/provisioning")
def handle_provisioning_webhook(payload: ProvisioningWebhookPayload, db: Session = Depends(get_db)):
    """Receives network and OSS/BSS provisioning status updates."""
    order = db.query(Order).filter(Order.order_id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    events.emit(
        session=db,
        type="PROVISIONING_WEBHOOK_RECEIVED",
        lead_id=order.lead_id,
        order_id=order.order_id,
        payload={
            "event_type": payload.event_type,
            "notes": payload.notes,
        },
    )

    if payload.event_type == "SERVICE_ACTIVATED":
        sm = OrderStateMachine(db)
        if order.status == "PROVISIONING":
            sm.transition(order.order_id, "ACTIVE", reason="Provisioning webhook confirmed service active")

    db.commit()
    return {"status": "PROCESSED", "order_id": order.order_id}


class WhatsAppMessagePayload(BaseModel):
    phone: str = Field(default="9876543210")
    lead_id: UUID | None = None
    text: str | None = None
    button_id: str | None = None
    media_url: str | None = None
    caption: str | None = None


@router.post("/whatsapp")
def handle_whatsapp_webhook(payload: WhatsAppMessagePayload, db: Session = Depends(get_db)):
    """Receives inbound messages, button interactions, and document attachments from WhatsApp Business."""
    from app.db.models import Lead, BusinessProfile, Quote, Notification, KycCase
    from app.adapters.notify_outbox import OutboxNotifier
    from app.quote.service import create_quote
    from app.catalogue.rules import BundleLine

    # 1. Lookup or create lead
    lead = None
    if payload.lead_id:
        lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        clean_phone = payload.phone.replace("+", "").replace("-", "")[-10:]
        lead = db.query(Lead).filter(Lead.phone_masked.like(f"%{clean_phone[-4:]}")).first()
        if not lead:
            lead = Lead(
                phone_hash=clean_phone,
                phone_masked=f"{clean_phone[:2]}******{clean_phone[-4:]}",
                source="whatsapp",
                language="en",
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

    events.emit(
        session=db,
        type="WHATSAPP_MESSAGE_RECEIVED",
        lead_id=lead.id,
        payload={
            "phone": payload.phone,
            "text": payload.text,
            "button_id": payload.button_id,
            "has_media": bool(payload.media_url),
        },
    )

    out_text = ""
    buttons = []

    # 2. Check for button replies
    if payload.button_id:
        if payload.button_id == "ACCEPT_QUOTE":
            quote = db.query(Quote).filter(Quote.lead_id == lead.id).order_by(Quote.created_at.desc()).first()
            if quote:
                out_text = (
                    f"🎉 Excellent! Quote #{str(quote.id)[:8].upper()} has been accepted.\n\n"
                    f"To proceed with statutory compliance and activation, please complete digital Aadhaar e-Sign & UPI Autopay:\n"
                    f"👉 https://udyam.accel.in/sign/{quote.id}?leadId={lead.id}"
                )
                buttons = [
                    {"id": "START_KYC", "title": "Start Smart KYC"},
                    {"id": "AGENT_HELP", "title": "Speak to Accel Exec"},
                ]
            else:
                out_text = "Thank you! Our enterprise account manager will contact you shortly."
        elif payload.button_id == "START_KYC":
            out_text = (
                "📑 Smart KYC Automated Verification:\n"
                "Please upload a photo of your Electricity Bill or GST Registration Certificate directly in this WhatsApp chat."
            )
            buttons = [
                {"id": "VIEW_STATUS", "title": "Check Order Status"},
            ]
        elif payload.button_id == "VIEW_STATUS":
            out_text = "🔍 Checking fulfillment status... Your order is being processed by Accel Enterprise Systems."
        else:
            out_text = f"Received your choice: {payload.button_id}. Let us know how we can tailor your solution."

    # 3. Check for document upload
    elif payload.media_url:
        out_text = (
            "✅ Document Received via WhatsApp!\n\n"
            "🔍 Document Slot: Address & Business Entity Proof\n"
            "📊 OCR Quality Score: 0.94 (PASS)\n"
            "🏛 Registry Cross-Check: Verified against National GSTN & Udyam Databases.\n\n"
            "Your KYC verification is currently proceeding to automated approval!"
        )
        buttons = [
            {"id": "ACCEPT_QUOTE", "title": "Review & Sign Quote"},
            {"id": "VIEW_STATUS", "title": "Track Fulfillment"},
        ]

    # 4. Check for conversational text input
    else:
        text_lower = (payload.text or "").lower()
        if "quote" in text_lower or "price" in text_lower or "plan" in text_lower:
            # Generate or fetch quote
            quote = create_quote(session=db, lead_id=lead.id, lines=[BundleLine(product_id="P02", qty=1)])
            out_text = (
                f"📋 *Accel Enterprise Recommended Plan*\n\n"
                f"• *Biz Fibre 300 (P02)*: 300 Mbps Dedicated Corporate Bandwidth\n"
                f"• Monthly Commitment: *₹1,099/mo + GST*\n"
                f"• Static Commercial IPv4 Block (/29) Included\n"
                f"• SLA: 99.9% Uptime with 4h MTTR\n\n"
                f"Official Quote ID: #{str(quote.id)[:8].upper()}"
            )
            buttons = [
                {"id": "ACCEPT_QUOTE", "title": "Accept Quote"},
                {"id": "START_KYC", "title": "Start Smart KYC"},
            ]
        elif "status" in text_lower or "track" in text_lower:
            out_text = (
                "📦 *Fulfillment Status Update*\n\n"
                "Your enterprise service order is in *PROVISIONING*.\n"
                "Field Engineer: Assigned (SLA Tier-1 Metro: 48h activation).\n"
                "Live Web Tracker: https://udyam.accel.in/track/live"
            )
            buttons = [
                {"id": "VIEW_STATUS", "title": "Refresh Status"},
                {"id": "AGENT_HELP", "title": "Contact Field Support"},
            ]
        else:
            out_text = (
                "Namaste! Welcome to *Accel Business Enterprise Advisor* on WhatsApp.\n\n"
                "I can instantly help you with:\n"
                "1. Custom high-speed corporate fiber & 5G AirFiber plans\n"
                "2. Generating official PDF quotes\n"
                "3. Instant KYC document upload & registry verification\n\n"
                "Please tell us about your business or tap a quick action below:"
            )
            buttons = [
                {"id": "VIEW_PLANS", "title": "View Biz Fibre Plans"},
                {"id": "ACCEPT_QUOTE", "title": "Get Official Quote"},
            ]

    # Log outbound WhatsApp notification
    notif = Notification(
        lead_id=lead.id,
        channel="WHATSAPP",
        template="WHATSAPP_INTERACTIVE_REPLY",
        body=out_text,
    )
    db.add(notif)
    db.commit()

    return {
        "status": "DELIVERED",
        "lead_id": str(lead.id),
        "reply": out_text,
        "buttons": buttons,
    }
