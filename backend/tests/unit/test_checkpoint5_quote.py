import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.db.models import Lead, BusinessProfile, Quote, QuoteLine, Event
from app.catalogue.rules import BundleLine
from app.quote.service import (
    create_quote,
    update_quote,
    amend_quote_for_invalid_gstin,
    accept_quote,
)
from app.quote.pdf import generate_quote_pdf_bytes
from app.main import app

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_lead(db_session):
    lead = Lead(
        id=uuid4(),
        source="web",
        language="en",
        phone_masked="******3210",
        status="NEW",
    )
    db_session.add(lead)

    bp = BusinessProfile(
        lead_id=lead.id,
        business_type="Bakery",
        segment="micro",
        city="Lucknow",
        tier=2,
        employees=4,
        sites=1,
        has_gstin=True,
        monthly_spend=3500,
    )
    db_session.add(bp)
    db_session.commit()
    return lead


def test_quote_creation(db_session, test_lead):
    """Verifies quote creation, line items, pricing, and event emission."""
    lines = [
        BundleLine(product_id="P01", qty=1),
        BundleLine(product_id="P07", qty=2),
    ]

    quote = create_quote(db_session, test_lead.id, lines, term_months=12)

    assert quote.id is not None
    assert quote.lead_id == test_lead.id
    assert quote.version == 1
    assert quote.term_months == 12
    assert quote.monthly_recurring > 0
    assert quote.first_month_total == quote.monthly_recurring + quote.one_time
    assert len(quote.lines) == 2

    # Verify event emission
    event = (
        db_session.query(Event)
        .filter(Event.lead_id == test_lead.id, Event.type == "QUOTE_CREATED")
        .first()
    )
    assert event is not None
    assert event.payload["quote_id"] == str(quote.id)


def test_addon_toggling_and_base_link_cascade_removal(db_session, test_lead):
    """Verifies adding add-ons, and cascade-dropping dependants when base link P01 is removed."""
    # 1. Start with base P01
    quote = create_quote(db_session, test_lead.id, [BundleLine(product_id="P01", qty=1)], term_months=12)
    assert len(quote.lines) == 1

    # 2. Add dependent P09 (Backup 4G/5G Failover)
    quote, changes = update_quote(db_session, quote.id, add_products=["P09"])
    pids = [l.product_id for l in quote.lines]
    assert "P01" in pids
    assert "P09" in pids
    assert len(quote.lines) == 2

    # 3. Explicitly remove base link P01 -> P09 must be cascade-dropped!
    quote, changes = update_quote(db_session, quote.id, remove_products=["P01"])
    pids_after = [l.product_id for l in quote.lines]
    assert "P01" not in pids_after
    assert "P09" not in pids_after  # Cascade dropped!
    assert any(c["reason"] == "DEPENDENT_DROPPED_ON_BASE_REMOVAL" for c in changes)


def test_quote_savings_calculation(db_session, test_lead):
    """Verifies savings calculation against current monthly spend."""
    lines = [BundleLine(product_id="P01", qty=1)]
    quote = create_quote(db_session, test_lead.id, lines, term_months=12)

    # test_lead monthly_spend is 3500. quote.monthly_recurring is ~1079.
    assert quote.savings_vs_current == (3500 - quote.monthly_recurring)
    assert quote.savings_vs_current > 0

    # If monthly spend is lower than recurring, savings should be None
    bp = db_session.query(BusinessProfile).filter(BusinessProfile.lead_id == test_lead.id).first()
    bp.monthly_spend = 500
    db_session.commit()

    quote2, _ = update_quote(db_session, quote.id, term_months=12)
    assert quote2.savings_vs_current is None


def test_quote_amendment_for_invalid_gstin(db_session, test_lead):
    """Verifies creating a new version when KYC discovers an invalid GSTIN."""
    # Create initial quote with leased line P05 (requires GSTIN)
    quote = create_quote(db_session, test_lead.id, [BundleLine(product_id="P05", qty=1)], term_months=12)
    assert quote.version == 1

    # KYC triggers amendment
    new_quote = amend_quote_for_invalid_gstin(db_session, quote.id)

    assert new_quote.version == 2
    assert new_quote.status == "DRAFT"
    assert quote.status == "SUPERSEDED"

    # P05 must not be in new quote because has_valid_gstin is False
    new_pids = [l.product_id for l in new_quote.lines]
    assert "P05" not in new_pids


def test_pdf_byte_generation(db_session, test_lead):
    """Verifies PDF document generation produces valid PDF bytes."""
    lines = [
        BundleLine(product_id="P01", qty=1),
        BundleLine(product_id="P07", qty=2),
    ]
    quote = create_quote(db_session, test_lead.id, lines, term_months=12)
    bp = db_session.query(BusinessProfile).filter(BusinessProfile.lead_id == test_lead.id).first()

    pdf_bytes = generate_quote_pdf_bytes(quote, test_lead, bp)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_esign_and_upi_mandate_api(db_session, test_lead):
    """Verifies e-sign workflow and UPI autopay mandate API."""
    lines = [BundleLine(product_id="P01", qty=1)]
    quote = create_quote(db_session, test_lead.id, lines, term_months=12)

    # 1. Request e-sign
    esign_resp = client.post(
        f"/esign/{quote.id}/request",
        json={"signatory_phone": "9876543210", "signatory_name": "Ramesh Kumar"},
    )
    assert esign_resp.status_code == 200
    esign_data = esign_resp.json()
    assert esign_data["status"] == "sent"
    esign_id = esign_data["esign_id"]

    # 2. Complete e-sign
    comp_resp = client.post(f"/esign/{esign_id}/complete")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # 3. Create UPI Mandate
    mandate_resp = client.post(
        "/payments/mandate",
        json={
            "quote_id": str(quote.id),
            "lead_id": str(test_lead.id),
            "vpa": "ramesh@okhdfcbank",
            "bank_name": "HDFC Bank",
        },
    )
    assert mandate_resp.status_code == 200
    mandate_data = mandate_resp.json()
    assert mandate_data["status"] == "success"
    assert mandate_data["event"] == "MANDATE_OK"
    assert mandate_data["mandate_id"].startswith("UMRN-")
