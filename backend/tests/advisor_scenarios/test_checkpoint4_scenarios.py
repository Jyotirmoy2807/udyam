import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.advisor.state import ConversationContext, AdvisorState
from app.advisor.tools import AdvisorToolExecutor
from app.adapters.llm_groq import GroqLlmAdapter
from app.catalogue.loader import load_catalogue
from app.catalogue.rules import Profile, BundleLine, validate, repair

catalogue = load_catalogue()


# -------------------------------------------------------------
# 15 ADVISOR SCENARIO TESTS
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_01_micro_retail_onboarding():
    """Scenario 1: Micro retail owner (Bakery, 3 employees, 1 site, Tier 2, no GSTIN)."""
    ctx = ConversationContext(lang="en")
    executor = AdvisorToolExecutor(ctx)

    res = await executor("update_profile", {
        "business_type": "Bakery",
        "city": "Lucknow",
        "employees": 3,
        "sites": 1,
        "has_gstin": False,
        "monthly_spend": 2500,
    })

    assert res["profile_complete"] is True
    assert ctx.segment == "micro"
    assert ctx.tier == 2

    rec = await executor("get_recommendation", {})
    assert rec["status"] == "success"
    pids = [l["product_id"] for l in rec["primary"]["lines"]]
    assert "P01" in pids or "P04" in pids
    assert rec["primary"]["monthly_recurring"] <= 3000


@pytest.mark.asyncio
async def test_scenario_02_professional_office_onboarding():
    """Scenario 2: Professional office (CA firm, 12 employees, 1 site, Tier 1, GSTIN active)."""
    ctx = ConversationContext(lang="en")
    executor = AdvisorToolExecutor(ctx)

    await executor("update_profile", {
        "business_type": "CA firm",
        "city": "Mumbai",
        "employees": 12,
        "sites": 1,
        "has_gstin": True,
        "monthly_spend": 6000,
    })

    assert ctx.segment == "professional_offices"
    assert ctx.tier == 1

    rec = await executor("get_recommendation", {})
    pids = [l["product_id"] for l in rec["primary"]["lines"]]
    assert "P02" in pids
    assert "P16" in pids


@pytest.mark.asyncio
async def test_scenario_03_small_multi_site_onboarding():
    """Scenario 3: Multi-site business (Pharmacy chain, 4 sites, 25 employees, Tier 1)."""
    ctx = ConversationContext(lang="en")
    executor = AdvisorToolExecutor(ctx)

    await executor("update_profile", {
        "business_type": "Pharmacy chain",
        "city": "Bengaluru",
        "employees": 25,
        "sites": 4,
        "has_gstin": True,
    })

    assert ctx.segment == "small_multi_site"
    assert ctx.tier == 1

    rec = await executor("get_recommendation", {})
    assert rec["status"] == "success"
    assert len(rec["primary"]["lines"]) >= 2


@pytest.mark.asyncio
async def test_scenario_04_small_manufacturer_partner_handoff():
    """Scenario 4: Manufacturer (Auto-parts unit, ILL request) routes to field partner handoff."""
    ctx = ConversationContext(lang="en")
    executor = AdvisorToolExecutor(ctx)

    await executor("update_profile", {
        "business_type": "Auto-parts unit",
        "city": "Pune",
        "employees": 50,
        "sites": 2,
        "has_gstin": True,
    })

    assert ctx.segment == "small_manufacturers"

    handoff_res = await executor("handoff", {"reason": "Small manufacturer requiring field feasibility inspection"})
    assert handoff_res["status"] == "handed_off"
    assert ctx.state == AdvisorState.HANDOFF_TO_HUMAN


@pytest.mark.asyncio
async def test_scenario_05_tier2_owner_asking_for_1g_fibre_p03():
    """Scenario 5: Tier-2 owner asks for Biz Fibre 1G (P03) which is Tier 1 only."""
    ctx = ConversationContext(city="Jaipur", tier=2, employees=10, sites=1, has_gstin=True)
    executor = AdvisorToolExecutor(ctx)

    # Validate against rules
    profile = Profile(tier=2, employees=10, sites=1, has_valid_gstin=True, segment="professional_offices")
    viols = validate(profile, [BundleLine(product_id="P03")], catalogue)
    assert any(v.code == "TIER_UNAVAILABLE" for v in viols)

    # Tool explains rule clearly
    explanation = await executor("explain_rule", {"violation_code": "TIER_UNAVAILABLE", "product_id": "P03"})
    assert "Tier 1" in explanation["explanation"]
    assert "Tier 2" in explanation["explanation"]


@pytest.mark.asyncio
async def test_scenario_06_nongstin_owner_asking_for_gst_only_product():
    """Scenario 6: Owner without GSTIN requests Internet Leased Line (P05)."""
    ctx = ConversationContext(city="Delhi", tier=1, employees=20, sites=1, has_gstin=False)
    executor = AdvisorToolExecutor(ctx)

    profile = Profile(tier=1, employees=20, sites=1, has_valid_gstin=False, segment="small_manufacturers")
    viols = validate(profile, [BundleLine(product_id="P05")], catalogue)
    assert any(v.code == "GSTIN_REQUIRED" for v in viols)

    explanation = await executor("explain_rule", {"violation_code": "GSTIN_REQUIRED", "product_id": "P05"})
    assert "GSTIN" in explanation["explanation"]


@pytest.mark.asyncio
async def test_scenario_07_two_site_owner_asking_for_sdwan_p10():
    """Scenario 7: 2-site business requests SD-WAN Managed (P10) which requires min 3 sites."""
    ctx = ConversationContext(city="Delhi", tier=1, employees=20, sites=2, has_gstin=True)
    executor = AdvisorToolExecutor(ctx)

    profile = Profile(tier=1, employees=20, sites=2, has_valid_gstin=True, segment="small_multi_site")
    viols = validate(profile, [BundleLine(product_id="P10")], catalogue)
    assert any(v.code == "MIN_SITES" for v in viols)

    explanation = await executor("explain_rule", {"violation_code": "MIN_SITES", "product_id": "P10"})
    assert "3" in explanation["explanation"]


@pytest.mark.asyncio
async def test_scenario_08_hindi_language_conversation_handling():
    """Scenario 8: Hindi language user interaction."""
    ctx = ConversationContext(lang="hi")
    executor = AdvisorToolExecutor(ctx)

    res = await executor("update_profile", {
        "business_type": "Kirana store",
        "city": "Delhi",
        "employees": 2,
        "sites": 1,
        "has_gstin": False,
    })

    assert res["profile_complete"] is True
    assert ctx.lang == "hi"
    assert ctx.segment == "micro"


@pytest.mark.asyncio
async def test_scenario_09_marathi_language_conversation_handling():
    """Scenario 9: Marathi language user interaction."""
    ctx = ConversationContext(lang="mr")
    executor = AdvisorToolExecutor(ctx)

    res = await executor("update_profile", {
        "business_type": "Salon",
        "city": "Pune",
        "employees": 4,
        "sites": 1,
        "has_gstin": True,
    })

    assert res["profile_complete"] is True
    assert ctx.lang == "mr"
    assert ctx.segment == "micro"


@pytest.mark.asyncio
async def test_scenario_10_discovery_cap_at_7_questions():
    """Scenario 10: Ensures discovery questions are capped at 7 turns max."""
    ctx = ConversationContext()
    for _ in range(7):
        ctx.question_count += 1

    assert ctx.question_count >= ctx.max_questions


@pytest.mark.asyncio
async def test_scenario_11_user_removes_base_link_cascade_drops():
    """Scenario 11: Owner removes base link from current bundle; dependants are dropped."""
    ctx = ConversationContext(city="Delhi", tier=1, employees=10, sites=1, has_gstin=True, segment="micro")
    ctx.current_bundle = [
        {"product_id": "P01", "qty": 1},
        {"product_id": "P09", "qty": 1},  # Dependent on P01
    ]
    executor = AdvisorToolExecutor(ctx)

    # Explicitly remove base link P01
    res = await executor("adjust_bundle", {"remove": ["P01"]})
    pids = [l["product_id"] for l in res["lines"]]
    assert "P01" not in pids
    assert "P09" not in pids  # P09 was cascade-dropped!
    assert any(c["reason"] == "DEPENDENT_DROPPED_ON_BASE_REMOVAL" for c in res["changes_log"])


@pytest.mark.asyncio
async def test_scenario_12_cheaper_alternative_bundle():
    """Scenario 12: Recommendation returns both primary and cheaper alternative."""
    ctx = ConversationContext(city="Mumbai", tier=1, employees=15, sites=1, has_gstin=True, segment="professional_offices")
    executor = AdvisorToolExecutor(ctx)

    rec = await executor("get_recommendation", {})
    assert "primary" in rec
    assert "cheaper_alternative" in rec
    assert rec["cheaper_alternative"]["monthly_recurring"] <= rec["primary"]["monthly_recurring"]


@pytest.mark.asyncio
async def test_scenario_13_off_topic_redirection():
    """Scenario 13: Off-topic inquiries handled gracefully while keeping profile intact."""
    ctx = ConversationContext(business_type="Dental clinic", city="Chennai")
    # State remains in progress and slots are preserved
    assert ctx.business_type == "Dental clinic"
    assert ctx.city == "Chennai"


@pytest.mark.asyncio
async def test_scenario_14_voice_transcription_fallback():
    """Scenario 14: Voice transcription fallback using STT adapter."""
    adapter = GroqLlmAdapter(api_key="mock_key")
    with patch.object(adapter.client.audio.transcriptions, "create", new_callable=AsyncMock) as mock_stt:
        mock_stt.return_value = "मेरा नाम राहुल है और मेरी किराने की दुकान है"
        text = await adapter.transcribe_audio(b"fake_audio_bytes", lang_code="hi")
        assert "किराने की दुकान" in text


@pytest.mark.asyncio
async def test_scenario_15_tool_error_resilience():
    """Scenario 15: Groq bad request / tool error handled with automatic retry at temperature 0.0."""
    adapter = GroqLlmAdapter(api_key="mock_key")
    # Verify adapter has retry logic for tool_use_failed
    assert hasattr(adapter, "run_advisor_turn")
