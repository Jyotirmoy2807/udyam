"""Funnel analytics queries calculated strictly over the immutable events table."""

from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import distinct, func
from app.db.models import Event


def get_funnel_metrics(db: Session) -> dict[str, Any]:
    """Computes end-to-end conversion funnel metrics and drop-off rates across stages."""
    # 1. Total Leads Created
    leads_count = (
        db.query(func.count(distinct(Event.lead_id)))
        .filter(Event.type == "LEAD_CREATED")
        .scalar()
        or 0
    )

    # 2. Profile Completed
    profile_count = (
        db.query(func.count(distinct(Event.lead_id)))
        .filter(Event.type.in_(["PROFILE_COMPLETED", "ADVISOR_PROFILE_UPDATED"]))
        .scalar()
        or 0
    )

    # 3. Quote Generated
    quote_count = (
        db.query(func.count(distinct(Event.lead_id)))
        .filter(Event.type == "QUOTE_CREATED")
        .scalar()
        or 0
    )

    # 4. KYC Passed
    kyc_passed_count = (
        db.query(func.count(distinct(Event.lead_id)))
        .filter(Event.type == "KYC_VERIFIED")
        .filter(Event.payload["verdict"].astext == "PASS")
        .scalar()
        or 0
    )

    # 5. Order Activated
    order_active_count = (
        db.query(func.count(distinct(Event.lead_id)))
        .filter(Event.type == "ORDER_STATE_CHANGED")
        .filter(Event.payload["to_status"].astext == "ACTIVE")
        .scalar()
        or 0
    )

    stages = [
        {"stage": "1_LEADS", "count": leads_count},
        {"stage": "2_PROFILE_COMPLETED", "count": profile_count},
        {"stage": "3_QUOTE_GENERATED", "count": quote_count},
        {"stage": "4_KYC_PASSED", "count": kyc_passed_count},
        {"stage": "5_ORDER_ACTIVE", "count": order_active_count},
    ]

    # Compute drop-off and conversion rates
    conversion_rates = {}
    prev_count = None
    for item in stages:
        s_name = item["stage"]
        cnt = item["count"]
        if leads_count > 0:
            item["overall_conversion_pct"] = round((cnt / leads_count) * 100.0, 2)
        else:
            item["overall_conversion_pct"] = 0.0

        if prev_count is not None and prev_count > 0:
            drop_pct = round(((prev_count - cnt) / prev_count) * 100.0, 2)
            item["stage_drop_off_pct"] = max(0.0, drop_pct)
        else:
            item["stage_drop_off_pct"] = 0.0

        prev_count = cnt

    return {
        "funnel_summary": {
            "total_leads": leads_count,
            "active_orders": order_active_count,
            "overall_conversion_pct": (
                round((order_active_count / leads_count) * 100.0, 2) if leads_count > 0 else 0.0
            ),
        },
        "stages": stages,
    }
