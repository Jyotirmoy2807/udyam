from dataclasses import dataclass, field
from typing import Any
from app.catalogue.loader import ProductRecord, load_catalogue


@dataclass(frozen=True)
class Profile:
    tier: int
    employees: int
    sites: int
    has_valid_gstin: bool
    segment: str


@dataclass(frozen=True)
class BundleLine:
    product_id: str
    qty: int = 1


@dataclass(frozen=True)
class Violation:
    product_id: str
    code: str  # TIER_UNAVAILABLE, MIN_EMPLOYEES, MIN_SITES, GSTIN_REQUIRED, DEPENDENCY_MISSING
    detail: dict[str, Any]


@dataclass
class RepairResult:
    lines: list[BundleLine]
    violations: list[Violation]
    changes_log: list[dict[str, Any]]


def compute_default_qty(
    product: ProductRecord,
    profile: Profile,
    mobile_lines: int | None = None,
) -> int:
    unit = product.unit.lower()
    if "site" in unit:
        return max(1, profile.sites)
    if "user" in unit or "device" in unit:
        return max(1, profile.employees)
    if "line" in unit:
        if mobile_lines is not None and mobile_lines > 0:
            return mobile_lines
        return min(10, max(1, profile.employees))
    if "camera" in unit:
        return 4
    if "counter" in unit:
        return max(1, profile.sites)
    if "vehicle" in unit:
        return 1
    # per number, per IP, per account, per pack -> 1
    return 1


def compute_default_term_months(
    lines: list[BundleLine],
    catalogue: dict[str, ProductRecord] | None = None,
) -> int:
    cat = catalogue or load_catalogue()
    term = 12
    for line in lines:
        prod = cat.get(line.product_id)
        if prod and prod.min_contract_months > term:
            term = prod.min_contract_months
    return term


def validate(
    profile: Profile,
    lines: list[BundleLine],
    catalogue: dict[str, ProductRecord] | None = None,
) -> list[Violation]:
    cat = catalogue or load_catalogue()
    violations: list[Violation] = []
    bundle_pids = {line.product_id for line in lines}

    for line in lines:
        pid = line.product_id
        prod = cat.get(pid)
        if not prod:
            violations.append(Violation(
                product_id=pid,
                code="UNKNOWN_PRODUCT",
                detail={"message": f"Product {pid} not found in catalogue"},
            ))
            continue

        # 1. City Tier availability
        if profile.tier not in prod.city_tier_availability:
            violations.append(Violation(
                product_id=pid,
                code="TIER_UNAVAILABLE",
                detail={
                    "current_tier": profile.tier,
                    "available_tiers": prod.city_tier_availability,
                },
            ))

        # 2. Min employees constraint
        if profile.employees < prod.min_employees:
            violations.append(Violation(
                product_id=pid,
                code="MIN_EMPLOYEES",
                detail={
                    "current_employees": profile.employees,
                    "min_required": prod.min_employees,
                },
            ))

        # 3. Min sites constraint
        if profile.sites < prod.min_sites:
            violations.append(Violation(
                product_id=pid,
                code="MIN_SITES",
                detail={
                    "current_sites": profile.sites,
                    "min_required": prod.min_sites,
                },
            ))

        # 4. GSTIN requirement
        if prod.requires_gstin == "Y" and not profile.has_valid_gstin:
            violations.append(Violation(
                product_id=pid,
                code="GSTIN_REQUIRED",
                detail={"requires_gstin": True, "has_valid_gstin": False},
            ))

        # 5. Dependency constraint (requires_one_of)
        if prod.requires_one_of:
            has_dep = any(req in bundle_pids for req in prod.requires_one_of)
            if not has_dep:
                violations.append(Violation(
                    product_id=pid,
                    code="DEPENDENCY_MISSING",
                    detail={"requires_one_of": prod.requires_one_of},
                ))

    return violations


def is_product_eligible(
    pid: str,
    profile: Profile,
    catalogue: dict[str, ProductRecord],
) -> bool:
    """Checks standalone eligibility of a product for the profile without dependencies."""
    prod = catalogue.get(pid)
    if not prod:
        return False
    if profile.tier not in prod.city_tier_availability:
        return False
    if profile.employees < prod.min_employees:
        return False
    if profile.sites < prod.min_sites:
        return False
    if prod.requires_gstin == "Y" and not profile.has_valid_gstin:
        return False
    return True


def repair(
    profile: Profile,
    lines: list[BundleLine],
    catalogue: dict[str, ProductRecord] | None = None,
    intent: str = "recommend",
) -> RepairResult:
    cat = catalogue or load_catalogue()
    current_lines = list(lines)
    changes_log: list[dict[str, Any]] = []

    for _pass in range(3):
        violations = validate(profile, current_lines, cat)
        if not violations:
            break

        # Group violations by product
        viol_map: dict[str, list[Violation]] = {}
        for v in violations:
            viol_map.setdefault(v.product_id, []).append(v)

        # Step 1: Drop products failing intrinsic eligibility constraints
        intrinsic_codes = {"TIER_UNAVAILABLE", "MIN_EMPLOYEES", "MIN_SITES", "GSTIN_REQUIRED", "UNKNOWN_PRODUCT"}
        to_drop = set()

        for pid, p_viols in viol_map.items():
            intrinsic = [v for v in p_viols if v.code in intrinsic_codes]
            if intrinsic:
                to_drop.add(pid)
                changes_log.append({
                    "action": "drop",
                    "product_id": pid,
                    "reason": intrinsic[0].code,
                    "detail": intrinsic[0].detail,
                    "pass": _pass + 1,
                })

        if to_drop:
            current_lines = [l for l in current_lines if l.product_id not in to_drop]
            continue

        # Step 2: Handle DEPENDENCY_MISSING
        dep_viols = [v for v in violations if v.code == "DEPENDENCY_MISSING"]
        if dep_viols:
            current_pids = {l.product_id for l in current_lines}
            for v in dep_viols:
                pid = v.product_id
                prod = cat.get(pid)
                if not prod or not prod.requires_one_of:
                    continue

                if intent == "user_removed_base":
                    # Cascade drop dependant when user deliberately removed base
                    current_lines = [l for l in current_lines if l.product_id != pid]
                    changes_log.append({
                        "action": "cascade_drop",
                        "product_id": pid,
                        "reason": "DEPENDENT_DROPPED_ON_BASE_REMOVAL",
                        "detail": {"missing_dependencies": prod.requires_one_of},
                        "pass": _pass + 1,
                    })
                else:
                    # intent == "recommend": find cheapest eligible base product
                    eligible_bases = []
                    for base_pid in prod.requires_one_of:
                        if is_product_eligible(base_pid, profile, cat):
                            base_prod = cat[base_pid]
                            eligible_bases.append((base_prod.price_min, base_pid, base_prod))

                    if eligible_bases:
                        eligible_bases.sort(key=lambda x: x[0])
                        chosen_base_pid = eligible_bases[0][1]
                        chosen_base_prod = eligible_bases[0][2]

                        if chosen_base_pid not in current_pids:
                            qty = compute_default_qty(chosen_base_prod, profile)
                            current_lines.append(BundleLine(product_id=chosen_base_pid, qty=qty))
                            current_pids.add(chosen_base_pid)
                            changes_log.append({
                                "action": "add_base_link",
                                "product_id": chosen_base_pid,
                                "reason": "DEPENDENCY_AUTO_REPAIR",
                                "detail": {"added_for": pid, "price_min": chosen_base_prod.price_min},
                                "pass": _pass + 1,
                            })
                    else:
                        # No base link is eligible -> drop the dependant
                        current_lines = [l for l in current_lines if l.product_id != pid]
                        changes_log.append({
                            "action": "drop",
                            "product_id": pid,
                            "reason": "NO_ELIGIBLE_DEPENDENCY_BASE",
                            "detail": {"allowed_bases": prod.requires_one_of},
                            "pass": _pass + 1,
                        })

    final_violations = validate(profile, current_lines, cat)
    return RepairResult(
        lines=current_lines,
        violations=final_violations,
        changes_log=changes_log,
    )


def recommend(
    profile: Profile,
    needs: list[str] | None = None,
    catalogue: dict[str, ProductRecord] | None = None,
) -> RepairResult:
    """Generates a legally compliant bundle guaranteed to pass validate()."""
    cat = catalogue or load_catalogue()
    needs = needs or []
    lines: list[BundleLine] = []

    # Choose eligible base link based on segment and profile
    base_candidate = "P01"
    if profile.tier == 1 and profile.segment in ("professional_offices", "small_multi_site"):
        base_candidate = "P02"
    elif profile.segment == "small_manufacturers":
        base_candidate = "P05"

    if is_product_eligible(base_candidate, profile, cat):
        lines.append(BundleLine(
            product_id=base_candidate,
            qty=compute_default_qty(cat[base_candidate], profile),
        ))
    else:
        # Fallback to cheapest eligible base
        for candidate in ["P04", "P01", "P02", "P05"]:
            if is_product_eligible(candidate, profile, cat):
                lines.append(BundleLine(
                    product_id=candidate,
                    qty=compute_default_qty(cat[candidate], profile),
                ))
                break

    # Add mobile / communication
    if is_product_eligible("P07", profile, cat):
        lines.append(BundleLine(
            product_id="P07",
            qty=compute_default_qty(cat["P07"], profile),
        ))

    # Add cloud collaboration / security if eligible
    if profile.segment != "micro" and is_product_eligible("P16", profile, cat):
        lines.append(BundleLine(
            product_id="P16",
            qty=compute_default_qty(cat["P16"], profile),
        ))

    # Run repair to guarantee 0 violations
    return repair(profile, lines, cat, intent="recommend")
