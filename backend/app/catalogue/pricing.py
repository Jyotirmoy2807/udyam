from dataclasses import dataclass, field
from typing import Any
from app.catalogue.loader import ProductRecord, load_catalogue
from app.catalogue.rules import BundleLine, Profile


@dataclass(frozen=True)
class PriceLine:
    product_id: str
    product_name: str
    qty: int
    unit_price: int
    line_monthly: int
    line_setup: int
    min_contract_months: int


@dataclass(frozen=True)
class BundleQuotePrice:
    term_months: int
    monthly_recurring: int
    one_time: int
    first_month_total: int
    savings_vs_current: int | None
    annual_savings: int | None
    lines: list[PriceLine]
    allowed_numbers: list[int] = field(default_factory=list)


def calculate_unit_price(
    product: ProductRecord,
    segment: str,
    term_months: int,
    qty: int,
) -> int:
    """Calculates position-based unit price according to pricing policy."""
    pos = 0.50
    if term_months >= 24:
        pos -= 0.15
    if qty >= 5:
        pos -= 0.10
    if segment == "micro":
        pos -= 0.10

    pos = min(0.90, max(0.10, pos))
    return round(product.price_min + pos * (product.price_max - product.price_min))


def price_bundle(
    lines: list[BundleLine],
    segment: str,
    term_months: int = 12,
    current_spend: int | None = None,
    catalogue: dict[str, ProductRecord] | None = None,
) -> BundleQuotePrice:
    cat = catalogue or load_catalogue()
    priced_lines: list[PriceLine] = []
    allowed_numbers: set[int] = set()

    total_monthly = 0
    total_setup = 0

    for line in lines:
        prod = cat.get(line.product_id)
        if not prod:
            continue

        unit_p = calculate_unit_price(
            product=prod,
            segment=segment,
            term_months=term_months,
            qty=line.qty,
        )
        line_monthly = unit_p * line.qty
        line_setup = prod.setup_fee * line.qty

        total_monthly += line_monthly
        total_setup += line_setup

        allowed_numbers.add(unit_p)
        allowed_numbers.add(line_monthly)
        allowed_numbers.add(line_setup)
        allowed_numbers.add(prod.price_min)
        allowed_numbers.add(prod.price_max)
        allowed_numbers.add(prod.setup_fee)

        priced_lines.append(PriceLine(
            product_id=prod.product_id,
            product_name=prod.name,
            qty=line.qty,
            unit_price=unit_p,
            line_monthly=line_monthly,
            line_setup=line_setup,
            min_contract_months=prod.min_contract_months,
        ))

    first_month = total_monthly + total_setup

    savings: int | None = None
    annual_savings: int | None = None
    if current_spend is not None and current_spend > total_monthly:
        savings = current_spend - total_monthly
        annual_savings = savings * 12
        allowed_numbers.add(current_spend)
        allowed_numbers.add(savings)
        allowed_numbers.add(annual_savings)

    allowed_numbers.add(total_monthly)
    allowed_numbers.add(total_setup)
    allowed_numbers.add(first_month)
    allowed_numbers.add(term_months)

    return BundleQuotePrice(
        term_months=term_months,
        monthly_recurring=total_monthly,
        one_time=total_setup,
        first_month_total=first_month,
        savings_vs_current=savings,
        annual_savings=annual_savings,
        lines=priced_lines,
        allowed_numbers=sorted(list(allowed_numbers)),
    )
