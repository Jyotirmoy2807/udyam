import pytest
from app.advisor.guardrail import AdvisorGuardrail, normalize_indic_digits


def test_indic_digits_normalization():
    # Hindi Devanagari 1299
    text_devanagari = "कीमत ₹१२९९ प्रति माह है।"
    normalized = normalize_indic_digits(text_devanagari)
    assert "₹1299" in normalized

    # Marathi Devanagari 959
    text_marathi = "दरमहा ₹९५९ फक्त"
    normalized_mr = normalize_indic_digits(text_marathi)
    assert "₹959" in normalized_mr


def test_guardrail_blocks_hallucinated_product_id():
    """Proves that an unapproved product ID like P99 triggers a block and deterministic fallback."""
    allowed_products = {"P01", "P07", "P19"}
    allowed_numbers = {1079, 299, 1500, 2878}
    guardrail = AdvisorGuardrail(allowed_products=allowed_products, allowed_numbers=allowed_numbers)

    hallucinated_reply = (
        "We recommend adding our special premium tier product P99 to your bundle for ₹1079 per month."
    )
    result = guardrail.evaluate(hallucinated_reply, lang="en")

    assert not result.is_valid
    assert result.fallback_used
    assert "P99" in result.hallucinated_products
    assert "customized Airtel Business Digital Bundle" in result.sanitized_content


def test_guardrail_blocks_fake_price():
    """Proves that a fake price (e.g. ₹999 instead of calculated ₹1079) is blocked."""
    allowed_products = {"P01", "P07"}
    allowed_numbers = {1079, 299, 1378}
    guardrail = AdvisorGuardrail(allowed_products=allowed_products, allowed_numbers=allowed_numbers)

    fake_price_reply = (
        "Your Biz Fibre P01 connection is available for just ₹999 per month!"
    )
    result = guardrail.evaluate(fake_price_reply, lang="en")

    assert not result.is_valid
    assert result.fallback_used
    assert 999 in result.hallucinated_numbers
    assert "customized Airtel Business Digital Bundle" in result.sanitized_content


def test_guardrail_blocks_devanagari_hallucinated_price():
    """Proves that an Indic script fake price (₹९९९) is caught after normalization."""
    allowed_products = {"P01"}
    allowed_numbers = {1079}
    guardrail = AdvisorGuardrail(allowed_products=allowed_products, allowed_numbers=allowed_numbers)

    hindi_reply = "इस प्लान की कीमत ₹९९९ प्रति माह होगी।"
    result = guardrail.evaluate(hindi_reply, lang="hi")

    assert not result.is_valid
    assert result.fallback_used
    assert 999 in result.hallucinated_numbers
    assert "सत्यापित एयरटेल बिजनेस डिजिटल बंडल" in result.sanitized_content


def test_guardrail_allows_strictly_compliant_content():
    """Proves that valid responses referencing only allowed products and verified prices pass unchanged."""
    allowed_products = {"P01", "P07"}
    allowed_numbers = {1079, 299, 1378}
    guardrail = AdvisorGuardrail(allowed_products=allowed_products, allowed_numbers=allowed_numbers)

    valid_reply = (
        "Your recommended bundle includes P01 (Biz Fibre 100) at ₹1079/month and P07 at ₹299/month, "
        "giving a total monthly recurring charge of ₹1378."
    )
    result = guardrail.evaluate(valid_reply, lang="en")

    assert result.is_valid
    assert not result.fallback_used
    assert result.sanitized_content == valid_reply
