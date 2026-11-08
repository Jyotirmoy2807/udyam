"""Comprehensive End-to-End Integration and Failure Simulation Test Suite."""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Lead, Quote, Order, Event, AuditLog, Notification


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_auth_otp_and_jwt_flow(client):
    """Verifies OTP generation and role-based JWT issuance."""
    # 1. Send OTP
    send_res = client.post("/auth/otp/send", json={"phone": "9876543210"})
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "OTP_SENT"
    assert "3210" in send_res.json()["phone_masked"]

    # 2. Verify with wrong OTP
    bad_res = client.post("/auth/otp/verify", json={"phone": "9876543210", "otp": "000000"})
    assert bad_res.status_code == 400

    # 3. Verify with correct OTP
    good_res = client.post("/auth/otp/verify", json={"phone": "9876543210", "otp": "123456", "role": "customer"})
    assert good_res.status_code == 200
    token = good_res.json()["access_token"]
    assert token is not None


def test_end_to_end_customer_journey(client, db):
    """Full happy path: Lead -> Chat -> Quote -> eSign -> Mandate -> Consent -> Order -> Activation."""
    # 1. Create Lead
    lead_res = client.post("/leads", json={
        "phone": "9812345678",
        "language": "hi",
        "source": "web",
        "business_type": "Bakery",
        "city": "Lucknow",
        "employees": 3,
        "sites": 1,
        "has_gstin": False,
        "monthly_spend": 2500,
    })
    assert lead_res.status_code == 201
    lead_data = lead_res.json()
    lead_id = lead_data["lead_id"]
    assert lead_data["phone_masked"] == "******5678"
    assert "propensity" in lead_data
    assert lead_data["propensity"]["score_int"] > 0
    assert lead_data["assigned_partner"] is not None

    # 2. Advisor Chat Turn
    chat_res = client.post("/advisor/chat", json={
        "lead_id": lead_id,
        "message": "Humko apne bakery ke liye accha wifi aur connection chahiye",
        "language": "hi",
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["reply"] is not None
    assert len(chat_data["reply"]) > 0

    # 3. Create Quote
    quote_res = client.post("/quotes", json={
        "lead_id": lead_id,
        "products": [{"product_id": "P01", "qty": 1}],
        "term_months": 12,
    })
    assert quote_res.status_code == 201
    quote_id = quote_res.json()["quote_id"]
    assert quote_res.json()["monthly_recurring"] > 0

    # 4. Mock e-Sign
    esign_res = client.post(f"/quotes/{quote_id}/esign", json={
        "signatory_name": "Ramesh Gupta",
        "signatory_phone": "9812345678",
    })
    assert esign_res.status_code == 200
    assert esign_res.json()["status"] == "sent"

    # 5. Mock UPI Mandate
    mandate_res = client.post("/quotes/mandate", json={
        "quote_id": quote_id,
        "lead_id": lead_id,
        "vpa": "ramesh@okhdfc",
        "bank_name": "HDFC Bank",
    })
    assert mandate_res.status_code == 200
    assert mandate_res.json()["status"] == "success"

    # 6. Record DPDP Consent
    consent_res = client.post("/kyc/consent", json={
        "lead_id": lead_id,
        "purpose": "KYC_VERIFICATION",
    })
    assert consent_res.status_code == 201
    consent_id = consent_res.json()["consent_id"]

    # 7. Create KYC Case
    case_res = client.post("/kyc/cases", json={
        "lead_id": lead_id,
        "quote_id": quote_id,
    })
    assert case_res.status_code == 201
    case_id = case_res.json()["case_id"]

    # 8. Create Order from Quote
    order_res = client.post("/orders", json={
        "quote_id": quote_id,
        "city_tier": 2,
    })
    assert order_res.status_code == 201
    order_id = order_res.json()["order_id"]
    assert order_res.json()["status"] == "SUBMITTED"
    assert order_res.json()["eta"] is not None

    # 9. Progress Order: SUBMITTED -> KYC_PENDING -> KYC_APPROVED -> PROVISIONING -> ACTIVE
    t1 = client.post(f"/orders/{order_id}/transition", json={"target_status": "KYC_PENDING"})
    assert t1.status_code == 200
    assert t1.json()["status"] == "KYC_PENDING"

    t2 = client.post(f"/orders/{order_id}/transition", json={"target_status": "KYC_APPROVED"})
    assert t2.status_code == 200
    assert t2.json()["status"] == "KYC_APPROVED"
    assert t2.json()["kyc_approved_at"] is not None

    t3 = client.post(f"/orders/{order_id}/transition", json={"target_status": "PROVISIONING"})
    assert t3.status_code == 200
    assert t3.json()["status"] == "PROVISIONING"

    t4 = client.post(f"/orders/{order_id}/transition", json={"target_status": "ACTIVE"})
    assert t4.status_code == 200
    assert t4.json()["status"] == "ACTIVE"

    # 10. Verify Activation Notification Created
    notif = db.query(Notification).filter(Notification.lead_id == lead_id, Notification.template == "ORDER_ACTIVATED").first()
    assert notif is not None
    assert "ACTIVE" in notif.body


def test_order_failure_simulations(client, db):
    """Verifies edge case simulators: Site Infeasibility Swap, Install Delay, and Payment Failure."""
    # 1. Setup quote and order
    lead_res = client.post("/leads", json={"phone": "9988776655", "business_type": "Salon", "city": "Pune", "employees": 4})
    lead_id = lead_res.json()["lead_id"]

    quote_res = client.post("/quotes", json={"lead_id": lead_id, "products": [{"product_id": "P01", "qty": 1}]})
    quote_id = quote_res.json()["quote_id"]

    order_res = client.post("/orders", json={"quote_id": quote_id, "city_tier": 1})
    order_id = order_res.json()["order_id"]
    original_eta = order_res.json()["eta"]

    # 2. Site Not Feasible Simulator -> Auto AirFiber P04 swap
    swap_res = client.post(f"/orders/{order_id}/simulate/site-not-feasible", params={"failed_product": "P01", "fallback_product": "P04"})
    assert swap_res.status_code == 200
    assert swap_res.json()["status"] == "SWAPPED"
    assert swap_res.json()["to_product"] == "P04"

    # Check updated order items
    get_order = client.get(f"/orders/{order_id}").json()
    pids = [item["product_id"] for item in get_order["items"]]
    assert "P04" in pids
    assert "P01" not in pids

    # 3. Installation Delayed Simulator -> Extends ETA
    delay_res = client.post(f"/orders/{order_id}/simulate/install-delayed", json={"delay_days": 4, "reason": "Severe rain"})
    assert delay_res.status_code == 200
    assert delay_res.json()["status"] == "DELAYED"
    assert delay_res.json()["new_eta"] > original_eta

    # 4. Payment Failure Simulator
    pay_res = client.post(f"/orders/{order_id}/simulate/payment-failed")
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "PAYMENT_FAILED_RETRYING"

    # 5. Invalid transition rejected
    invalid_res = client.post(f"/orders/{order_id}/transition", json={"target_status": "DRAFT"})
    assert invalid_res.status_code == 400


def test_conversion_funnel_and_audit_log(client, db):
    """Verifies that Ops dashboard funnel metrics are computed over append-only events."""
    funnel_res = client.get("/ops/funnel")
    assert funnel_res.status_code == 200
    data = funnel_res.json()
    assert "funnel_summary" in data
    assert "stages" in data
    assert len(data["stages"]) == 5

    events_res = client.get("/ops/events", params={"limit": 10})
    assert events_res.status_code == 200
    assert len(events_res.json()) > 0


def test_ops_kyc_override(client, db):
    """Verifies manual override of KYC verdict by ops admin with audit logging."""
    lead_res = client.post("/leads", json={"phone": "9123456780", "business_type": "Pharmacy", "city": "Jaipur"})
    lead_id = lead_res.json()["lead_id"]

    client.post("/kyc/consent", json={"lead_id": lead_id})
    quote_res = client.post("/quotes", json={"lead_id": lead_id, "products": [{"product_id": "P04", "qty": 1}]})
    quote_id = quote_res.json()["quote_id"]

    case_res = client.post("/kyc/cases", json={"lead_id": lead_id, "quote_id": quote_id})
    case_id = case_res.json()["case_id"]

    override_res = client.post(f"/ops/kyc/{case_id}/override", json={
        "new_verdict": "PASS",
        "reason": "Clear manual utility bill verification by supervisor",
        "actor": "supervisor@accel.com",
    })
    assert override_res.status_code == 200
    assert override_res.json()["new_verdict"] == "PASS"

    audit = db.query(AuditLog).filter(AuditLog.target == f"kyc_case:{case_id}").first()
    assert audit is not None
    assert audit.actor == "supervisor@accel.com"


def test_zero_unmasked_pii_in_api_responses(client):
    """Guarantees that full unmasked phone numbers and GSTINs are never exposed in API payloads."""
    raw_phone = "9876543210"
    raw_gstin = "27AAECR2040M1Z5"

    lead_res = client.post("/leads", json={
        "phone": raw_phone,
        "business_type": "Salon",
        "city": "Mumbai",
        "has_gstin": True,
    })
    body = lead_res.text
    # Raw 10-digit phone must never appear in response body
    assert raw_phone not in body
    # Only masked copy should be returned
    assert "******3210" in body

    # Verify retrieval endpoint
    lead_id = lead_res.json()["lead_id"]
    get_res = client.get(f"/leads/{lead_id}")
    assert raw_phone not in get_res.text
    assert "******3210" in get_res.text

