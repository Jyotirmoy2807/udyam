"""Inbound webhook handlers for e-sign, UPI autopay mandate, and network provisioning."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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
    umn: str = "airtel.mandate@upi"


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
