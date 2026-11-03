"""Deterministic SLA ETA computation based on product catalogue and city tier."""

from datetime import date, timedelta
from typing import Any
from sqlalchemy.orm import Session
from app.db.models import Product


def calculate_install_days(typical_install_days: int, city_tier: int = 1) -> int:
    """Computes installation days considering city tier.
    Tier 1 = standard typical install days.
    Tier 2 = standard typical install days + 2.
    """
    tier_offset = 2 if city_tier == 2 else 0
    return max(1, typical_install_days + tier_offset)


def compute_order_eta(
    db: Session,
    product_ids: list[str],
    city_tier: int = 1,
    start_date: date | None = None,
) -> tuple[date, dict[str, date]]:
    """Calculates deterministic SLA ETA for the order and individual products.

    Returns:
        tuple[date, dict[str, date]]: (max_order_eta, {product_id: item_eta})
    """
    if start_date is None:
        start_date = date(2026, 7, 15)

    products = db.query(Product).filter(Product.product_id.in_(product_ids)).all()
    product_map = {p.product_id: p.typical_install_days for p in products}

    item_etas: dict[str, date] = {}
    max_days = 1

    for pid in product_ids:
        typical_days = product_map.get(pid, 3)
        effective_days = calculate_install_days(typical_days, city_tier)
        item_eta = start_date + timedelta(days=effective_days)
        item_etas[pid] = item_eta
        if effective_days > max_days:
            max_days = effective_days

    order_eta = start_date + timedelta(days=max_days)
    return order_eta, item_etas
