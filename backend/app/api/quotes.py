from typing import Any
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Quote, Lead, BusinessProfile
from app.catalogue.rules import BundleLine
from app.quote.service import create_quote, update_quote, accept_quote, amend_quote_for_invalid_gstin
from app.quote.pdf import generate_quote_pdf_bytes
from app.adapters.notify_outbox import OutboxNotifier
from app.events import emit

router = APIRouter(tags=["Quotes & Checkout"])


class CreateQuoteRequest(BaseModel):
    lead_id: UUID
    products: list[dict[str, Any]]  # [{"product_id": "P01", "qty": 1}]
    term_months: int | None = None


class UpdateQuoteRequest(BaseModel):
    add_products: list[str] | None = None
    remove_products: list[str] | None = None
    qty_updates: dict[str, int] | None = None
    term_months: int | None = None


class EsignRequest(BaseModel):
    signatory_phone: str | None = None
    signatory_name: str | None = None


class MandateRequest(BaseModel):
    quote_id: UUID
    lead_id: UUID
    vpa: str = Field(description="Customer UPI Virtual Payment Address (e.g. user@okhdfc)")
    bank_name: str | None = "HDFC Bank"
    max_amount: int | None = None


@router.post("/quotes", status_code=status.HTTP_201_CREATED)
def api_create_quote(req: CreateQuoteRequest, db: Session = Depends(get_db)):
    lines = [BundleLine(product_id=p["product_id"], qty=p.get("qty", 1)) for p in req.products]
    quote = create_quote(db, req.lead_id, lines, req.term_months)
    return {
        "quote_id": quote.id,
        "lead_id": quote.lead_id,
        "version": quote.version,
        "term_months": quote.term_months,
        "monthly_recurring": quote.monthly_recurring,
        "one_time": quote.one_time,
        "first_month_total": quote.first_month_total,
        "savings_vs_current": quote.savings_vs_current,
        "status": quote.status,
    }


@router.get("/quotes/{quote_id}")
def api_get_quote(quote_id: UUID, db: Session = Depends(get_db)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lines = []
    for ql in quote.lines:
        lines.append({
            "product_id": ql.product_id,
            "name": ql.product.name if ql.product else ql.product_id,
            "category": ql.product.category if ql.product else None,
            "qty": ql.qty,
            "unit_price": ql.unit_price,
            "line_monthly": ql.line_monthly,
            "setup": ql.setup,
            "reason_codes": ql.reason_codes,
        })

    return {
        "quote_id": quote.id,
        "lead_id": quote.lead_id,
        "version": quote.version,
        "term_months": quote.term_months,
        "monthly_recurring": quote.monthly_recurring,
        "one_time": quote.one_time,
        "first_month_total": quote.first_month_total,
        "savings_vs_current": quote.savings_vs_current,
        "status": quote.status,
        "lines": lines,
    }


@router.get("/products")
def api_get_products(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    products = query.order_by(Product.product_id).all()
    return [
        {
            "product_id": p.product_id,
            "name": p.name,
            "category": p.category,
            "description": p.description,
            "unit": p.unit,
            "price_min": p.price_min,
            "price_max": p.price_max,
            "setup_fee": p.setup_fee,
            "requires_gstin": p.requires_gstin,
            "requires_one_of": p.requires_one_of,
        }
        for p in products
    ]


@router.post("/quotes/{quote_id}/amend-gstin")
def api_amend_gstin(quote_id: UUID, db: Session = Depends(get_db)):
    try:
        new_quote = amend_quote_for_invalid_gstin(db, quote_id, reason="GSTIN cancelled in verification")
        return {
            "status": "AMENDED",
            "previous_quote_id": quote_id,
            "new_quote_id": new_quote.id,
            "version": new_quote.version,
            "monthly_recurring": new_quote.monthly_recurring,
            "one_time": new_quote.one_time,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/quotes/{quote_id}")
def api_update_quote(quote_id: UUID, req: UpdateQuoteRequest, db: Session = Depends(get_db)):
    try:
        quote, changes = update_quote(
            session=db,
            quote_id=quote_id,
            add_products=req.add_products,
            remove_products=req.remove_products,
            qty_updates=req.qty_updates,
            term_months=req.term_months,
        )
        return {
            "quote_id": quote.id,
            "version": quote.version,
            "monthly_recurring": quote.monthly_recurring,
            "one_time": quote.one_time,
            "first_month_total": quote.first_month_total,
            "savings_vs_current": quote.savings_vs_current,
            "changes_log": changes,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/quotes/{quote_id}/accept")
def api_accept_quote(quote_id: UUID, db: Session = Depends(get_db)):
    try:
        quote = accept_quote(db, quote_id)
        return {"status": "success", "quote_id": quote.id, "quote_status": quote.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/quotes/{quote_id}/pdf")
def api_get_quote_pdf(quote_id: UUID, db: Session = Depends(get_db)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lead = db.query(Lead).filter(Lead.id == quote.lead_id).first()
    profile = db.query(BusinessProfile).filter(BusinessProfile.lead_id == quote.lead_id).first()

    pdf_bytes = generate_quote_pdf_bytes(quote, lead, profile)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Accel_Quote_{quote_id}.pdf"},
    )


@router.post("/quotes/{quote_id}/esign")
@router.post("/esign/{quote_id}/request")
def api_request_esign(quote_id: UUID, req: EsignRequest, db: Session = Depends(get_db)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    esign_id = uuid4()
    notifier = OutboxNotifier(db)

    phone = req.signatory_phone or "the registered contact"
    notifier.send(
        lead_id=quote.lead_id,
        channel="sms",
        template="ESIGN_INVITE",
        body=f"Please sign your Accel Business Digital Bundle agreement: https://udyam.accel.in/sign/{esign_id}",
    )

    emit(
        session=db,
        type="ESIGN_REQUESTED",
        lead_id=quote.lead_id,
        payload={"quote_id": str(quote.id), "esign_id": str(esign_id), "target_phone": phone},
    )
    db.commit()
    return {"status": "sent", "esign_id": str(esign_id), "quote_id": str(quote.id)}


@router.post("/esign/{esign_id}/complete")
def api_complete_esign(esign_id: UUID, db: Session = Depends(get_db)):
    emit(
        session=db,
        type="ESIGN_COMPLETED",
        payload={"esign_id": str(esign_id), "method": "Aadhaar e-Sign"},
    )
    db.commit()
    return {"status": "completed", "esign_id": str(esign_id), "timestamp": "2026-07-15T10:00:00Z"}


@router.post("/quotes/mandate")
@router.post("/payments/mandate")
def api_create_mandate(req: MandateRequest, db: Session = Depends(get_db)):
    mandate_id = f"UMRN-{uuid4().hex[:12].upper()}"
    emit(
        session=db,
        type="MANDATE_OK",
        lead_id=req.lead_id,
        payload={
            "mandate_id": mandate_id,
            "quote_id": str(req.quote_id),
            "vpa": req.vpa,
            "bank_name": req.bank_name,
            "status": "ACTIVE",
        },
    )
    db.commit()
    return {
        "status": "success",
        "mandate_status": "ACTIVE",
        "mandate_id": mandate_id,
        "quote_id": str(req.quote_id),
        "vpa": req.vpa,
        "event": "MANDATE_OK",
    }
