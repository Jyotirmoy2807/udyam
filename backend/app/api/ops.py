"""Operations dashboard, funnel analytics, and audit logging router."""

from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Event, KycCase, AuditLog
from app.leads.funnel import get_funnel_metrics
from app.api.auth import require_role
from app import events

router = APIRouter(prefix="/ops", tags=["Operations & Audit"])


class KycOverrideRequest(BaseModel):
    new_verdict: str  # PASS or NEEDS_FIX
    reason: str
    actor: str = "ops_reviewer@airtel.com"


@router.get("/funnel")
def get_conversion_funnel(db: Session = Depends(get_db)):
    """Computes real-time conversion funnel and drop-off analytics over append-only events."""
    return get_funnel_metrics(db)


@router.get("/events")
def get_audit_events(
    lead_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Fetches recent immutable events from the append-only events log."""
    query = db.query(Event)
    if lead_id:
        query = query.filter(Event.lead_id == lead_id)
    if event_type:
        query = query.filter(Event.type == event_type)

    results = query.order_by(Event.ts.desc()).limit(limit).all()
    return [
        {
            "id": str(e.id),
            "ts": e.ts.isoformat(),
            "lead_id": str(e.lead_id) if e.lead_id else None,
            "order_id": str(e.order_id) if e.order_id else None,
            "type": e.type,
            "payload": e.payload,
        }
        for e in results
    ]


@router.post("/kyc/{case_id}/override")
def override_kyc_verdict(case_id: UUID, req: KycOverrideRequest, db: Session = Depends(get_db)):
    """Enables manual KYC override by ops supervisors, logging actor to immutable audit_log."""
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found.")

    if req.new_verdict not in ("PASS", "NEEDS_FIX"):
        raise HTTPException(status_code=400, detail="Override verdict must be 'PASS' or 'NEEDS_FIX'.")

    prev_verdict = case.verdict
    case.verdict = req.new_verdict
    case.decided_at = datetime.now(timezone.utc)

    # Log to AuditLog table
    audit = AuditLog(
        actor=req.actor,
        role="ops_admin",
        action="KYC_VERDICT_OVERRIDE",
        target=f"kyc_case:{case_id}",
        detail={
            "from_verdict": prev_verdict,
            "to_verdict": req.new_verdict,
            "reason": req.reason,
        },
    )
    db.add(audit)

    events.emit(
        session=db,
        type="KYC_VERDICT_OVERRIDDEN",
        lead_id=case.lead_id,
        payload={
            "case_id": str(case_id),
            "actor": req.actor,
            "from": prev_verdict,
            "to": req.new_verdict,
            "reason": req.reason,
        },
    )

    db.commit()
    return {
        "status": "OVERRIDDEN",
        "case_id": case_id,
        "new_verdict": case.verdict,
        "actor": req.actor,
    }
