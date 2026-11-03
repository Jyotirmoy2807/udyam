"""Lead management, scoring, and partner queue router."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Lead, BusinessProfile, LeadScore
from app.db.crypto import encrypt_field, mask_phone
from app.leads.propensity.score import predict_propensity
from app.leads.queue import assign_lead_to_partner, get_partner_queue
from app import events

router = APIRouter(prefix="/leads", tags=["Leads & CRM"])


class CreateLeadRequest(BaseModel):
    phone: str = Field(description="10-digit mobile number")
    language: str = Field(default="en")
    source: str = Field(default="web")
    business_type: str | None = None
    city: str | None = None
    employees: int = 1
    sites: int = 1
    has_gstin: bool = False
    monthly_spend: int | None = None
    current_internet: str | None = None
    current_provider: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_lead(req: CreateLeadRequest, db: Session = Depends(get_db)):
    """Creates a new lead, encrypts PII, calculates propensity, and assigns a partner."""
    lead = Lead(
        source=req.source,
        language=req.language,
        phone_enc=encrypt_field(req.phone),
        phone_masked=mask_phone(req.phone),
        status="NEW",
    )
    db.add(lead)
    db.flush()

    # Create business profile
    profile = BusinessProfile(
        lead_id=lead.id,
        business_type=req.business_type,
        city=req.city,
        tier=1 if req.city and req.city.strip().title() in ["Mumbai", "Delhi", "Bengaluru", "Kolkata", "Chennai", "Hyderabad", "Pune", "Ahmedabad", "Surat"] else 2,
        employees=req.employees,
        sites=req.sites,
        has_gstin=req.has_gstin,
        monthly_spend=req.monthly_spend,
        current_internet=req.current_internet,
        current_provider=req.current_provider,
    )
    db.add(profile)
    db.flush()

    # Calculate Propensity Score
    prop_data = {
        "employee_count": req.employees,
        "num_sites": req.sites,
        "monthly_telecom_spend_inr": req.monthly_spend or 1500,
        "business_type": req.business_type or "Bakery",
        "city_tier": profile.tier,
        "has_gstin": req.has_gstin,
        "current_provider": req.current_provider or "Competitor A",
        "current_internet": req.current_internet or "Home broadband",
        "segment": profile.segment or "micro",
    }
    prop_result = predict_propensity(prop_data)

    lead_score = LeadScore(
        lead_id=lead.id,
        score=prop_result["score_int"],
        model_version=prop_result["model_version"],
        top_factors=prop_result["top_factors"],
    )
    db.add(lead_score)

    events.emit(
        session=db,
        type="LEAD_CREATED",
        lead_id=lead.id,
        payload={
            "source": req.source,
            "language": req.language,
            "propensity_score": prop_result["score_int"],
            "decile": prop_result["decile"],
            "band": prop_result["band"],
        },
    )
    db.commit()

    # Assign to partner
    assigned_partner = assign_lead_to_partner(db, lead.id)

    return {
        "lead_id": lead.id,
        "status": lead.status,
        "phone_masked": lead.phone_masked,
        "language": lead.language,
        "propensity": prop_result,
        "assigned_partner": {
            "partner_id": assigned_partner.id if assigned_partner else None,
            "name": assigned_partner.name if assigned_partner else None,
        } if assigned_partner else None,
    }


@router.get("/{lead_id}")
def get_lead(lead_id: UUID, db: Session = Depends(get_db)):
    """Retrieves full lead context and profile."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    prof = lead.profile
    score_obj = db.query(LeadScore).filter(LeadScore.lead_id == lead_id).first()

    return {
        "lead_id": lead.id,
        "status": lead.status,
        "language": lead.language,
        "phone_masked": lead.phone_masked,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "profile": {
            "business_type": prof.business_type if prof else None,
            "segment": prof.segment if prof else None,
            "city": prof.city if prof else None,
            "tier": prof.tier if prof else None,
            "employees": prof.employees if prof else None,
            "sites": prof.sites if prof else None,
            "has_gstin": prof.has_gstin if prof else None,
            "monthly_spend": prof.monthly_spend if prof else None,
        } if prof else None,
        "score": {
            "score": score_obj.score,
            "model_version": score_obj.model_version,
            "top_factors": score_obj.top_factors,
        } if score_obj else None,
    }


@router.get("/queue/{partner_id}")
def get_queue(partner_id: UUID, db: Session = Depends(get_db)):
    """Retrieves assigned leads for a partner."""
    return get_partner_queue(db, partner_id)
