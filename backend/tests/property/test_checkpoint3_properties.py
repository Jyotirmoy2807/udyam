from hypothesis import given, strategies as st, settings as hyp_settings
from app.catalogue.loader import load_catalogue
from app.catalogue.rules import (
    Profile,
    BundleLine,
    validate,
    repair,
    recommend,
)

catalogue = load_catalogue()

# Hypothesis strategies for generating random business profiles
profile_strategy = st.builds(
    Profile,
    tier=st.integers(min_value=1, max_value=2),
    employees=st.integers(min_value=1, max_value=500),
    sites=st.integers(min_value=1, max_value=50),
    has_valid_gstin=st.booleans(),
    segment=st.sampled_from(["micro", "professional_offices", "small_multi_site", "small_manufacturers"]),
)

product_id_strategy = st.sampled_from(list(catalogue.keys()))
bundle_line_strategy = st.builds(
    BundleLine,
    product_id=product_id_strategy,
    qty=st.integers(min_value=1, max_value=20),
)
bundle_strategy = st.lists(bundle_line_strategy, min_size=1, max_size=8)


@hyp_settings(max_examples=100, deadline=None)
@given(profile=profile_strategy)
def test_recommend_always_passes_validate(profile):
    """Property 1: recommend() must always generate a bundle with ZERO violations for any valid profile."""
    result = recommend(profile=profile, catalogue=catalogue)
    violations = validate(profile, result.lines, catalogue)
    assert len(violations) == 0, f"Recommendation produced violations: {violations}"
    assert len(result.lines) > 0, "Recommendation must propose at least one product"


@hyp_settings(max_examples=100, deadline=None)
@given(
    profile=profile_strategy,
    lines=bundle_strategy,
    intent=st.sampled_from(["recommend", "user_removed_base"]),
)
def test_repair_is_idempotent(profile, lines, intent):
    """Property 2: repair(repair(lines)) == repair(lines).
    Applying repair a second time produces identical lines and 0 new changes."""
    first_repair = repair(profile, lines, catalogue, intent=intent)
    second_repair = repair(profile, first_repair.lines, catalogue, intent=intent)

    # Lines must be identical
    pids_1 = [(l.product_id, l.qty) for l in first_repair.lines]
    pids_2 = [(l.product_id, l.qty) for l in second_repair.lines]
    assert pids_1 == pids_2

    # Second pass must have 0 violations and 0 changes
    assert len(second_repair.violations) == 0
    assert len(second_repair.changes_log) == 0
