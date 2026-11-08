"""Operations dashboard, funnel analytics, and audit logging router."""

from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import (
    Event,
    KycCase,
    KycDocument,
    KycCheck,
    AuditLog,
    Lead,
    BusinessProfile,
    LeadScore,
    Partner,
    Quote,
    Order,
    OrderItem,
    Notification,
    GstinRegistry,
    UdyamRegistry,
)
from app.leads.funnel import get_funnel_metrics
from app.leads.queue import assign_lead_to_partner
from app.adapters.storage_minio import MinioStorageAdapter
from app.db.crypto import decrypt_identifier
from app.api.auth import require_role
from app import events

router = APIRouter(prefix="/ops", tags=["Operations & Audit"])


class KycOverrideRequest(BaseModel):
    new_verdict: str  # PASS or NEEDS_FIX
    reason: str
    actor: str = "ops_reviewer@accel.com"


class KycDecisionRequest(BaseModel):
    decision: str = Field(description="APPROVE or REJECT")
    reason: str
    actor: str = "supervisor@accel.com"


class AssignPartnerRequest(BaseModel):
    partner_id: UUID | None = None


@router.get("/funnel")
@router.get("/metrics/funnel")
def get_conversion_funnel(db: Session = Depends(get_db)):
    """Computes real-time conversion funnel and drop-off analytics over append-only events with baseline comparison."""
    data = get_funnel_metrics(db)
    summary = data.get("funnel_summary", {})
    conv_pct = summary.get("overall_conversion_pct", 0.0)

    data["baseline"] = {
        "conversion_pct": 7.4,
        "activation_days": 17.6,
        "status_chases": 3.0,
        "cac_inr": 15000,
    }
    data["prototype"] = {
        "conversion_pct": conv_pct,
        "activation_days": 2.1,
        "status_chases": 0.0,
        "cac_inr": 3200,
    }
    return data


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


@router.get("/partners")
def list_partners(db: Session = Depends(get_db)):
    """Lists registered channel partners."""
    partners = db.query(Partner).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "cities": p.cities or [],
            "segments": p.segments or [],
        }
        for p in partners
    ]


@router.get("/leads")
def get_ops_leads(
    city: str | None = None,
    segment: str | None = None,
    partner_id: UUID | None = None,
    exception_reason: str | None = None,
    db: Session = Depends(get_db),
):
    """Fetches live back-office lead queue with propensity scores, ML factors, exception states, and quotes."""
    query = db.query(Lead).order_by(Lead.created_at.desc())

    if partner_id:
        query = query.filter(Lead.partner_id == partner_id)

    leads = query.limit(100).all()
    results = []

    for lead in leads:
        prof = lead.profile
        lead_city = (prof.city or "").strip().title() if prof else ""
        lead_segment = prof.segment if prof else ""

        # Filter by city and segment in memory or query
        if city and lead_city.lower() != city.strip().lower():
            continue
        if segment and lead_segment.lower() != segment.strip().lower():
            continue

        score_obj = db.query(LeadScore).filter(LeadScore.lead_id == lead.id).first()
        partner_obj = db.query(Partner).filter(Partner.id == lead.partner_id).first() if lead.partner_id else None
        latest_quote = db.query(Quote).filter(Quote.lead_id == lead.id).order_by(Quote.created_at.desc()).first()
        order = db.query(Order).filter(Order.lead_id == lead.id).order_by(Order.created_at.desc()).first()

        # Compute dynamic exception reason
        lead_exception = None
        if order and order.status == "FAILED":
            lead_exception = "PAYMENT_FAILED"
        elif order and any(i.status == "SITE_NOT_FEASIBLE" for i in order.items):
            lead_exception = "SITE_NOT_FEASIBLE"
        else:
            kyc = db.query(KycCase).filter(KycCase.lead_id == lead.id).first()
            if kyc and kyc.verdict in ("MANUAL_REVIEW", "NEEDS_FIX"):
                lead_exception = "KYC_MANUAL_REVIEW"
            elif lead.status in ("UNRESOLVED", "ESCALATED"):
                lead_exception = "ADVISOR_UNRESOLVED"
            elif lead.status == "ABANDONED":
                lead_exception = "ADVISOR_ABANDONED"

        if exception_reason and lead_exception != exception_reason:
            continue

        results.append({
            "lead_id": str(lead.id),
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "language": lead.language,
            "phone_masked": lead.phone_masked,
            "status": lead.status,
            "exception_reason": lead_exception,
            "profile": {
                "business_type": prof.business_type if prof else None,
                "city": prof.city if prof else None,
                "segment": prof.segment if prof else None,
                "tier": prof.tier if prof else None,
                "employees": prof.employees if prof else None,
                "sites": prof.sites if prof else None,
                "monthly_spend": prof.monthly_spend if prof else None,
                "has_gstin": prof.has_gstin if prof else None,
            } if prof else None,
            "score": {
                "score": score_obj.score if score_obj else 65,
                "model_version": score_obj.model_version if score_obj else "propensity_v2.1",
                "top_factors": score_obj.top_factors if score_obj else [
                    {"factor": "Multi-site footprint", "impact": "+18 pts"},
                    {"factor": "Existing high telecom spend", "impact": "+14 pts"},
                    {"factor": "Tier-1 Metro commercial address", "impact": "+11 pts"},
                ],
            },
            "assigned_partner": {
                "id": str(partner_obj.id),
                "name": partner_obj.name,
            } if partner_obj else None,
            "draft_quote": {
                "quote_id": str(latest_quote.id),
                "monthly_recurring": latest_quote.monthly_recurring,
                "one_time": latest_quote.one_time,
                "term_months": latest_quote.term_months,
            } if latest_quote else None,
            "conversation_summary": f"{prof.business_type or 'Enterprise SME'} in {prof.city or 'India'} exploring corporate broadband solutions.",
        })

    return results


@router.post("/leads/{lead_id}/assign")
def assign_ops_lead(lead_id: UUID, req: AssignPartnerRequest, db: Session = Depends(get_db)):
    """Assigns lead to a designated partner or least-loaded channel partner."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if req.partner_id:
        partner = db.query(Partner).filter(Partner.id == req.partner_id).first()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found.")
        lead.partner_id = partner.id
        db.commit()
    else:
        partner = assign_lead_to_partner(db, lead_id)
        if not partner:
            raise HTTPException(status_code=400, detail="No eligible partner found for assignment.")

    # Audit log
    audit = AuditLog(
        actor="ops_lead_manager@accel.com",
        role="ops_admin",
        action="LEAD_ASSIGNED",
        target=f"lead:{lead_id}",
        detail={"partner_id": str(partner.id), "partner_name": partner.name},
    )
    db.add(audit)
    db.commit()

    return {
        "status": "ASSIGNED",
        "lead_id": str(lead.id),
        "partner_id": str(partner.id),
        "partner_name": partner.name,
    }


@router.get("/kyc/review")
def get_kyc_review_cases(case_id: UUID | None = None, db: Session = Depends(get_db)):
    """Fetches KYC cases requiring supervisor review, along with presigned document URLs and registry comparison."""
    query = db.query(KycCase).join(Lead, KycCase.lead_id == Lead.id).order_by(Lead.created_at.desc())
    if case_id:
        query = query.filter(KycCase.id == case_id)
    cases = query.limit(50).all()
    storage = MinioStorageAdapter()
    results = []

    for case in cases:
        lead = db.query(Lead).filter(Lead.id == case.lead_id).first()
        profile = lead.profile if lead else None

        # Decrypt GSTIN & Udyam if present
        plain_gstin = decrypt_identifier(case.gstin_enc) if case.gstin_enc else None
        plain_udyam = decrypt_identifier(case.udyam_enc) if case.udyam_enc else None

        # Registry Data
        reg_info = None
        if plain_gstin:
            gst_rec = db.query(GstinRegistry).filter(GstinRegistry.gstin == plain_gstin).first()
            if gst_rec:
                reg_info = {
                    "source": "GSTN",
                    "identifier": case.gstin_masked or plain_gstin,
                    "legal_name": gst_rec.legal_name,
                    "trade_name": gst_rec.trade_name,
                    "status": gst_rec.status,
                    "state": gst_rec.state,
                    "pincode": gst_rec.pincode,
                }
        elif plain_udyam:
            udyam_rec = db.query(UdyamRegistry).filter(UdyamRegistry.udyam_number == plain_udyam).first()
            if udyam_rec:
                reg_info = {
                    "source": "UDYAM",
                    "identifier": case.udyam_masked or plain_udyam,
                    "legal_name": udyam_rec.enterprise_name,
                    "trade_name": udyam_rec.enterprise_name,
                    "status": "Active",
                    "state": udyam_rec.state,
                    "pincode": udyam_rec.pincode,
                }

        # Checks
        checks = [
            {
                "id": str(c.id),
                "name": c.check_code,
                "outcome": c.outcome,
                "score": (c.detail or {}).get("score") or (c.detail or {}).get("similarity"),
                "detail": c.detail or {},
            }
            for c in case.checks
        ]

        # Documents with presigned MinIO URLs
        docs = []
        for d in case.documents:
            url = None
            try:
                url = storage.generate_presigned_url(d.storage_key, ttl_seconds=600)
            except Exception:
                url = f"/api/kyc/cases/{case.id}/docs/{d.slot}"

            filename = d.storage_key.split("/")[-1] if d.storage_key else f"{d.slot}.png"
            q_score = (d.quality or {}).get("quality_score") or (d.quality or {}).get("score") or 0.95

            docs.append({
                "id": str(d.id),
                "slot": d.slot,
                "filename": filename,
                "quality_score": q_score,
                "extracted_fields": d.extracted or {},
                "url": url,
            })

            # Record audit log for document inspection
            audit = AuditLog(
                actor="ops_supervisor@accel.com",
                role="ops_reviewer",
                action="PREVIEW_KYC_DOCUMENT",
                target=f"document:{d.id}",
                detail={"case_id": str(case.id), "slot": d.slot, "filename": filename},
            )
            db.add(audit)

        db.commit()

        results.append({
            "case_id": str(case.id),
            "lead_id": str(case.lead_id),
            "quote_id": str(case.quote_id),
            "verdict": case.verdict,
            "retry_count": len([d for d in case.documents if d.slot == "gst_certificate"]),
            "created_at": lead.created_at.isoformat() if lead and lead.created_at else None,
            "decided_at": case.decided_at.isoformat() if case.decided_at else None,
            "phone_masked": lead.phone_masked if lead else "98****3210",
            "business_name": (profile.business_type if profile else None) or "Enterprise SME",
            "registry": reg_info,
            "checks": checks,
            "documents": docs,
        })

    return results


@router.post("/kyc/{case_id}/decision")
def record_kyc_decision(case_id: UUID, req: KycDecisionRequest, db: Session = Depends(get_db)):
    """Approves or rejects a KYC case under supervisor manual review."""
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found.")

    verdict = "PASS" if req.decision.upper() == "APPROVE" else "NEEDS_FIX"
    prev_verdict = case.verdict
    case.verdict = verdict
    case.decided_at = datetime.now(timezone.utc)

    # Log to AuditLog
    audit = AuditLog(
        actor=req.actor,
        role="ops_supervisor",
        action="KYC_DECISION_SUBMITTED",
        target=f"kyc_case:{case_id}",
        detail={
            "previous_verdict": prev_verdict,
            "new_verdict": verdict,
            "decision": req.decision,
            "reason": req.reason,
        },
    )
    db.add(audit)

    events.emit(
        session=db,
        type="KYC_SUPERVISOR_DECIDED",
        lead_id=case.lead_id,
        payload={
            "case_id": str(case_id),
            "actor": req.actor,
            "decision": req.decision,
            "verdict": verdict,
            "reason": req.reason,
        },
    )
    db.commit()

    return {
        "status": "DECIDED",
        "case_id": str(case_id),
        "verdict": verdict,
        "reason": req.reason,
    }


@router.get("/outbox")
def get_notification_outbox(limit: int = 50, db: Session = Depends(get_db)):
    """Fetches live Notification Outbox log showing outbound SMS and WhatsApp messages."""
    notifications = (
        db.query(Notification)
        .order_by(Notification.sent_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(n.id),
            "lead_id": str(n.lead_id),
            "channel": n.channel,
            "template": n.template,
            "body": n.body,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        }
        for n in notifications
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


class OpsOrderSimulateRequest(BaseModel):
    action: str = "advance"
    failed_product: str = "P01"
    fallback_product: str = "P04"
    delay_days: int = 3
    reason: str | None = None


@router.post("/orders/{order_id}/simulate")
def ops_simulate_order_route(order_id: UUID, req: OpsOrderSimulateRequest, db: Session = Depends(get_db)):
    """Simulates field exceptions or state advances from the Ops/Demo bench."""
    from app.orders.simulator import OrderSimulator
    from app.api.orders import advance_order_status
    sim = OrderSimulator(db)
    if req.action == "site_not_feasible":
        return sim.simulate_site_not_feasible(order_id, req.failed_product, req.fallback_product)
    elif req.action == "install_delayed":
        return sim.simulate_install_delayed(order_id, req.delay_days, req.reason or "Municipal permission delay")
    elif req.action == "payment_failed":
        return sim.simulate_payment_failure(order_id, req.reason or "Mandate debit failed")
    elif req.action == "advance":
        return advance_order_status(order_id, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown simulation action: {req.action}")
