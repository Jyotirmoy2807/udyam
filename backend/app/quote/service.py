from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models import Quote, QuoteLine, Lead, BusinessProfile
from app.events import emit
from app.catalogue.loader import load_catalogue
from app.catalogue.rules import (
    Profile,
    BundleLine,
    validate,
    repair,
    compute_default_qty,
    compute_default_term_months,
)
from app.catalogue.pricing import price_bundle

catalogue = load_catalogue()


def get_profile_for_lead(session: Session, lead_id: UUID) -> Profile:
    lead = session.query(Lead).filter(Lead.id == lead_id).first()
    bp = session.query(BusinessProfile).filter(BusinessProfile.lead_id == lead_id).first()

    tier = bp.tier if bp and bp.tier else 2
    employees = bp.employees if bp and bp.employees else 1
    sites = bp.sites if bp and bp.sites else 1
    has_gstin = bp.has_gstin if bp else False
    segment = bp.segment if bp and bp.segment else "micro"

    return Profile(
        tier=tier,
        employees=employees,
        sites=sites,
        has_valid_gstin=has_gstin,
        segment=segment,
    )


def create_quote(
    session: Session,
    lead_id: UUID,
    lines: list[BundleLine],
    term_months: int | None = None,
) -> Quote:
    profile = get_profile_for_lead(session, lead_id)
    bp = session.query(BusinessProfile).filter(BusinessProfile.lead_id == lead_id).first()
    current_spend = bp.monthly_spend if bp else None

    # Determine contract term
    term = term_months or compute_default_term_months(lines, catalogue)

    # 1. Run deterministic repair
    repair_result = repair(profile, lines, catalogue, intent="recommend")

    # 2. Compute deterministic pricing
    pricing = price_bundle(
        lines=repair_result.lines,
        segment=profile.segment,
        term_months=term,
        current_spend=current_spend,
        catalogue=catalogue,
    )

    # 3. Create Quote entity
    quote = Quote(
        lead_id=lead_id,
        version=1,
        term_months=term,
        monthly_recurring=pricing.monthly_recurring,
        one_time=pricing.one_time,
        first_month_total=pricing.first_month_total,
        savings_vs_current=pricing.savings_vs_current,
        status="DRAFT",
    )
    session.add(quote)
    session.flush()

    # 4. Create QuoteLine entities
    for l in pricing.lines:
        ql = QuoteLine(
            quote_id=quote.id,
            product_id=l.product_id,
            qty=l.qty,
            unit_price=l.unit_price,
            line_monthly=l.line_monthly,
            setup=l.line_setup,
            reason_codes=[],
        )
        session.add(ql)

    # 5. Emit immutable event
    emit(
        session=session,
        type="QUOTE_CREATED",
        lead_id=lead_id,
        payload={
            "quote_id": str(quote.id),
            "version": quote.version,
            "monthly_recurring": quote.monthly_recurring,
            "one_time": quote.one_time,
            "first_month_total": quote.first_month_total,
            "term_months": quote.term_months,
            "savings_vs_current": quote.savings_vs_current,
        },
    )
    session.commit()
    return quote


def update_quote(
    session: Session,
    quote_id: UUID,
    add_products: list[str] | None = None,
    remove_products: list[str] | None = None,
    qty_updates: dict[str, int] | None = None,
    term_months: int | None = None,
) -> tuple[Quote, list[dict[str, Any]]]:
    quote = session.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    profile = get_profile_for_lead(session, quote.lead_id)
    bp = session.query(BusinessProfile).filter(BusinessProfile.lead_id == quote.lead_id).first()
    current_spend = bp.monthly_spend if bp else None

    remove_set = set(remove_products or [])
    qty_updates = qty_updates or {}
    term = term_months or quote.term_months

    # Check if a base connectivity product was explicitly removed by user
    base_pids = {"P01", "P02", "P03", "P04", "P05", "P06"}
    is_base_removal = bool(remove_set.intersection(base_pids))

    # Existing lines
    line_map: dict[str, int] = {ql.product_id: ql.qty for ql in quote.lines}

    # Apply removals
    for pid in remove_set:
        line_map.pop(pid, None)

    # Apply qty updates
    for pid, qty in qty_updates.items():
        if pid in line_map and qty > 0:
            line_map[pid] = qty

    # Apply additions
    for pid in (add_products or []):
        if pid in catalogue and pid not in line_map:
            line_map[pid] = compute_default_qty(catalogue[pid], profile)

    # Convert back to BundleLine
    candidate_lines = [BundleLine(product_id=p, qty=q) for p, q in line_map.items()]

    # Run repair with appropriate intent
    intent = "user_removed_base" if is_base_removal else "recommend"
    repair_result = repair(profile, candidate_lines, catalogue, intent=intent)

    # Re-price
    pricing = price_bundle(
        lines=repair_result.lines,
        segment=profile.segment,
        term_months=term,
        current_spend=current_spend,
        catalogue=catalogue,
    )

    # Delete existing lines and re-add updated lines
    session.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).delete()

    quote.term_months = term
    quote.monthly_recurring = pricing.monthly_recurring
    quote.one_time = pricing.one_time
    quote.first_month_total = pricing.first_month_total
    quote.savings_vs_current = pricing.savings_vs_current

    for l in pricing.lines:
        ql = QuoteLine(
            quote_id=quote.id,
            product_id=l.product_id,
            qty=l.qty,
            unit_price=l.unit_price,
            line_monthly=l.line_monthly,
            setup=l.line_setup,
            reason_codes=[],
        )
        session.add(ql)

    emit(
        session=session,
        type="QUOTE_UPDATED",
        lead_id=quote.lead_id,
        payload={
            "quote_id": str(quote.id),
            "monthly_recurring": quote.monthly_recurring,
            "one_time": quote.one_time,
            "first_month_total": quote.first_month_total,
            "savings_vs_current": quote.savings_vs_current,
            "changes_log": repair_result.changes_log,
        },
    )
    session.commit()
    return quote, repair_result.changes_log


def amend_quote_for_invalid_gstin(
    session: Session,
    quote_id: UUID,
    reason: str = "QUOTE_AMENDMENT_REQUIRED",
) -> Quote:
    """Creates a new version of the quote when KYC detects a Cancelled/Suspended GSTIN."""
    old_quote = session.query(Quote).filter(Quote.id == quote_id).first()
    if not old_quote:
        raise ValueError(f"Quote {quote_id} not found")

    old_quote.status = "SUPERSEDED"

    lead_profile = get_profile_for_lead(session, old_quote.lead_id)
    non_gst_profile = Profile(
        tier=lead_profile.tier,
        employees=lead_profile.employees,
        sites=lead_profile.sites,
        has_valid_gstin=False,  # Enforce False due to KYC finding
        segment=lead_profile.segment,
    )

    bp = session.query(BusinessProfile).filter(BusinessProfile.lead_id == old_quote.lead_id).first()
    if bp:
        bp.has_gstin = False

    current_lines = [BundleLine(product_id=ql.product_id, qty=ql.qty) for ql in old_quote.lines]
    # Repair with has_valid_gstin=False (auto-drops P05/P06 and substitutes compliant base links)
    repair_result = repair(non_gst_profile, current_lines, catalogue, intent="recommend")

    pricing = price_bundle(
        lines=repair_result.lines,
        segment=non_gst_profile.segment,
        term_months=old_quote.term_months,
        current_spend=bp.monthly_spend if bp else None,
        catalogue=catalogue,
    )

    new_quote = Quote(
        lead_id=old_quote.lead_id,
        version=old_quote.version + 1,
        term_months=old_quote.term_months,
        monthly_recurring=pricing.monthly_recurring,
        one_time=pricing.one_time,
        first_month_total=pricing.first_month_total,
        savings_vs_current=pricing.savings_vs_current,
        status="DRAFT",
    )
    session.add(new_quote)
    session.flush()

    for l in pricing.lines:
        ql = QuoteLine(
            quote_id=new_quote.id,
            product_id=l.product_id,
            qty=l.qty,
            unit_price=l.unit_price,
            line_monthly=l.line_monthly,
            setup=l.line_setup,
            reason_codes=["GSTIN_INVALID_AMENDMENT"],
        )
        session.add(ql)

    emit(
        session=session,
        type="QUOTE_AMENDED",
        lead_id=new_quote.lead_id,
        payload={
            "previous_quote_id": str(old_quote.id),
            "new_quote_id": str(new_quote.id),
            "version": new_quote.version,
            "reason": reason,
            "monthly_recurring": new_quote.monthly_recurring,
        },
    )
    session.commit()
    return new_quote


def accept_quote(session: Session, quote_id: UUID) -> Quote:
    quote = session.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    quote.status = "ACCEPTED"
    emit(
        session=session,
        type="QUOTE_ACCEPTED",
        lead_id=quote.lead_id,
        payload={"quote_id": str(quote.id), "version": quote.version},
    )
    session.commit()
    return quote
