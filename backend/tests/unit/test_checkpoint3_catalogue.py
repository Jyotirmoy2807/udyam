import pytest
import pandas as pd
from pathlib import Path

from app.catalogue.loader import load_catalogue, find_catalogue_csv
from app.catalogue.rules import (
    Profile,
    BundleLine,
    Violation,
    validate,
    repair,
    recommend,
    compute_default_qty,
    compute_default_term_months,
)
from app.catalogue.pricing import calculate_unit_price, price_bundle


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


# ---------------------------------------------------------
# 1. PARAMETRISED UNIT TESTS FOR ALL 5 VIOLATION CODES
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "line,profile,expected_code",
    [
        # 1. TIER_UNAVAILABLE: P03 (Biz Fibre 1Gbps) is Tier 1 only. In Tier 2 -> TIER_UNAVAILABLE
        (
            BundleLine(product_id="P03"),
            Profile(tier=2, employees=20, sites=1, has_valid_gstin=True, segment="professional_offices"),
            "TIER_UNAVAILABLE",
        ),
        # 2. MIN_EMPLOYEES: P06 (MPLS WAN) requires min 10 employees. With 5 -> MIN_EMPLOYEES
        (
            BundleLine(product_id="P06"),
            Profile(tier=1, employees=5, sites=2, has_valid_gstin=True, segment="small_manufacturers"),
            "MIN_EMPLOYEES",
        ),
        # 3. MIN_SITES: P10 (SD-WAN Managed) requires min 3 sites. With 2 -> MIN_SITES
        (
            BundleLine(product_id="P10"),
            Profile(tier=1, employees=25, sites=2, has_valid_gstin=True, segment="small_multi_site"),
            "MIN_SITES",
        ),
        # 4. GSTIN_REQUIRED: P05 (Internet Leased Line) requires GSTIN. Without active GSTIN -> GSTIN_REQUIRED
        (
            BundleLine(product_id="P05"),
            Profile(tier=1, employees=30, sites=2, has_valid_gstin=False, segment="small_manufacturers"),
            "GSTIN_REQUIRED",
        ),
        # 5. DEPENDENCY_MISSING: P09 (Backup 4G/5G) requires one of P01|P02|P03|P05|P06 base links
        (
            BundleLine(product_id="P09"),
            Profile(tier=1, employees=10, sites=1, has_valid_gstin=True, segment="professional_offices"),
            "DEPENDENCY_MISSING",
        ),
    ],
)
def test_all_five_violation_codes(catalogue, line, profile, expected_code):
    violations = validate(profile, [line], catalogue)
    codes = [v.code for v in violations]
    assert expected_code in codes


def test_repair_recommend_adds_cheapest_base_link(catalogue):
    """When a dependent product is in the bundle without a base link,
    intent='recommend' adds the cheapest eligible base link."""
    profile = Profile(tier=1, employees=10, sites=1, has_valid_gstin=True, segment="micro")
    lines = [BundleLine(product_id="P09")]  # requires P01|P02|P03|P05|P06

    result = repair(profile, lines, catalogue, intent="recommend")
    assert len(result.violations) == 0
    pids = [l.product_id for l in result.lines]
    assert "P09" in pids
    # P01 is cheapest eligible base link (price_min 799 vs P02 1299)
    assert "P01" in pids


def test_repair_user_removed_base_cascade_drops_dependents(catalogue):
    """When the user explicitly toggles off the base link,
    intent='user_removed_base' cascade-drops the orphaned dependent instead of re-adding base."""
    profile = Profile(tier=1, employees=10, sites=1, has_valid_gstin=True, segment="micro")
    lines = [BundleLine(product_id="P09")]  # dependent alone

    result = repair(profile, lines, catalogue, intent="user_removed_base")
    assert len(result.violations) == 0
    pids = [l.product_id for l in result.lines]
    assert "P09" not in pids
    assert len(result.lines) == 0
    assert any(c["reason"] == "DEPENDENT_DROPPED_ON_BASE_REMOVAL" for c in result.changes_log)


def test_pricing_calculation_and_policy(catalogue):
    """Verifies position calculation with -= on micro segment and bulk/term discounts."""
    prod = catalogue["P01"]  # min 999, max 1199

    # Standard 12m, micro (pos = 0.50 - 0.10 = 0.40)
    p_micro = calculate_unit_price(prod, segment="micro", term_months=12, qty=1)
    expected_micro = round(999 + 0.40 * (1199 - 999))  # 999 + 80 = 1079
    assert p_micro == expected_micro

    # 24m, micro, bulk 5+ (pos = 0.50 - 0.15 - 0.10 - 0.10 = 0.15)
    p_bulk = calculate_unit_price(prod, segment="micro", term_months=24, qty=5)
    expected_bulk = round(999 + 0.15 * (1199 - 999))  # 999 + 30 = 1029
    assert p_bulk == expected_bulk


# ---------------------------------------------------------
# 2. HISTORICAL REPLAY TEST ON 368 ACTIVATED BUNDLES
# ---------------------------------------------------------

def test_historical_replay_on_activated_bundles(catalogue):
    """Replays rules validation and setup fee calculation across all 368 historical
    activated bundles in smb_leads.csv.
    Verifies:
      1. Flags exactly 48 bundles containing 53 catalogue rule violations from manual sales.
      2. Matches setup fees for 100% of the 368 bundles (368 / 368).
    """
    leads_path = Path("data/smb_leads.csv")
    if not leads_path.exists():
        leads_path = Path("../data/smb_leads.csv")
    df = pd.read_csv(leads_path)
    activated = df[df["stage_reached"] == "Activated"]
    assert len(activated) == 368

    bundles_with_violations = []
    total_violations_count = 0
    setup_fee_matches = 0

    for _, row in activated.iterrows():
        lid = row["lead_id"]
        tier = int(row["city_tier"])
        employees = int(row["employee_count"])
        sites = int(row["num_sites"])
        has_gstin = str(row["has_gstin"]).strip().lower() in ("true", "yes", "1", "y")
        segment = str(row["segment"]).strip()

        profile = Profile(
            tier=tier,
            employees=employees,
            sites=sites,
            has_valid_gstin=has_gstin,
            segment=segment,
        )

        bundle_str = str(row["bundle_products"])
        lines: list[BundleLine] = []
        calc_setup = 0

        for item in bundle_str.split(";"):
            if not item.strip():
                continue
            parts = item.split("x")
            pid = parts[0].strip()
            qty = int(parts[1].strip()) if len(parts) > 1 else 1
            lines.append(BundleLine(product_id=pid, qty=qty))

            prod = catalogue.get(pid)
            if prod:
                calc_setup += prod.setup_fee * qty

        # 1. Check setup fee match
        expected_setup = int(row["one_time_setup_inr"])
        if calc_setup == expected_setup:
            setup_fee_matches += 1

        # 2. Check rule violations
        viols = validate(profile, lines, catalogue)
        if viols:
            bundles_with_violations.append((lid, viols))
            total_violations_count += len(viols)

    # Assert exactly 48 bundles and 53 violations
    assert len(bundles_with_violations) == 48, f"Expected 48 bundles with violations, got {len(bundles_with_violations)}"
    assert total_violations_count == 53, f"Expected 53 total violations, got {total_violations_count}"

    # Assert 100% setup fee match
    assert setup_fee_matches == 368, f"Expected 368 setup fee matches, got {setup_fee_matches}"
