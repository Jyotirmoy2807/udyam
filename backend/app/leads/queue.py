"""Partner assignment and lead queue management."""

from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Lead, Partner, BusinessProfile
from app import events


def assign_lead_to_partner(db: Session, lead_id: UUID) -> Partner | None:
    """Assigns lead to an eligible channel partner using least-loaded round-robin."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return None

    profile = db.query(BusinessProfile).filter(BusinessProfile.lead_id == lead_id).first()
    lead_city = (profile.city or "").strip().title() if profile else ""
    lead_segment = profile.segment if profile else ""

    all_partners = db.query(Partner).all()
    if not all_partners:
        return None

    # Filter partners by city and segment matching
    eligible_partners = []
    for partner in all_partners:
        p_cities = [c.strip().title() for c in (partner.cities or [])]
        p_segments = partner.segments or []

        city_match = not p_cities or lead_city in p_cities or "*" in p_cities
        segment_match = not p_segments or lead_segment in p_segments or "*" in p_segments

        if city_match and segment_match:
            eligible_partners.append(partner)

    if not eligible_partners:
        eligible_partners = all_partners

    # Pick partner with lowest current assigned lead count
    partner_counts = (
        db.query(Lead.partner_id, func.count(Lead.id))
        .filter(Lead.partner_id.in_([p.id for p in eligible_partners]))
        .group_by(Lead.partner_id)
        .all()
    )
    count_map = {p_id: count for p_id, count in partner_counts}

    best_partner = min(eligible_partners, key=lambda p: count_map.get(p.id, 0))

    lead.partner_id = best_partner.id
    events.emit(
        session=db,
        type="LEAD_ASSIGNED_TO_PARTNER",
        lead_id=lead.id,
        payload={
            "partner_id": str(best_partner.id),
            "partner_name": best_partner.name,
            "city": lead_city,
            "segment": lead_segment,
        },
    )
    db.commit()
    db.refresh(lead)
    return best_partner


def get_partner_queue(db: Session, partner_id: UUID) -> list[dict]:
    """Fetches queue of leads assigned to a specific partner."""
    leads = (
        db.query(Lead)
        .filter(Lead.partner_id == partner_id)
        .order_by(Lead.created_at.desc())
        .all()
    )
    results = []
    for lead in leads:
        prof = lead.profile
        results.append({
            "lead_id": str(lead.id),
            "status": lead.status,
            "language": lead.language,
            "phone_masked": lead.phone_masked,
            "business_type": prof.business_type if prof else None,
            "city": prof.city if prof else None,
            "tier": prof.tier if prof else None,
            "employees": prof.employees if prof else None,
            "sites": prof.sites if prof else None,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        })
    return results
