"""Unit tests for Checkpoint 8: Back-Office Lead Queue, KYC Supervisor Review, and WhatsApp Webhook."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Lead, KycCase, AuditLog, Notification, Partner


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


def test_ops_partners_list(client):
    """Verifies listing of registered channel partners."""
    res = client.get("/ops/partners")
    assert res.status_code == 200
    partners = res.json()
    assert isinstance(partners, list)
    if partners:
        assert "name" in partners[0]
        assert "cities" in partners[0]


def test_ops_lead_queue_and_partner_assignment(client, db):
    """Verifies lead queue filtering, propensity scores, and partner reassignment."""
    # 1. Create a lead
    lead_res = client.post("/leads", json={
        "phone": "9988776655",
        "business_type": "Retail Supermarket",
        "city": "Bengaluru",
        "employees": 15,
        "sites": 2,
        "has_gstin": True,
        "monthly_spend": 8500,
    })
    assert lead_res.status_code == 201
    lead_id = lead_res.json()["lead_id"]

    # 2. Fetch leads queue
    queue_res = client.get("/ops/leads")
    assert queue_res.status_code == 200
    leads = queue_res.json()
    assert len(leads) > 0
    target_lead = next((l for l in leads if l["lead_id"] == lead_id), None)
    assert target_lead is not None
    assert target_lead["score"]["score"] > 0
    assert "top_factors" in target_lead["score"]

    # 3. Filter by city
    blr_res = client.get("/ops/leads?city=Bengaluru")
    assert blr_res.status_code == 200
    assert any(l["lead_id"] == lead_id for l in blr_res.json())

    # 4. Assign lead to a partner
    assign_res = client.post(f"/ops/leads/{lead_id}/assign", json={})
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "ASSIGNED"
    assert "partner_id" in assign_res.json()

    # 5. Check AuditLog entry
    audit = db.query(AuditLog).filter(AuditLog.target == f"lead:{lead_id}").first()
    assert audit is not None
    assert audit.action == "LEAD_ASSIGNED"


def test_ops_kyc_supervisor_review_and_decision(client, db):
    """Verifies KYC manual review queue and supervisor approve/reject decisions."""
    # 1. Create lead and case
    lead_res = client.post("/leads", json={"phone": "9811223344", "city": "Mumbai"})
    lead_id = lead_res.json()["lead_id"]

    client.post("/kyc/consent", json={"lead_id": lead_id})
    quote_res = client.post("/quotes", json={"lead_id": lead_id, "products": [{"product_id": "P01", "qty": 1}]})
    quote_id = quote_res.json()["quote_id"]

    case_res = client.post("/kyc/cases", json={"lead_id": lead_id, "quote_id": quote_id})
    case_id = case_res.json()["case_id"]

    # 2. Query KYC review cases
    review_res = client.get("/ops/kyc/review")
    assert review_res.status_code == 200
    cases = review_res.json()
    print("Created case_id:", case_id, "Found cases:", [c["case_id"] for c in cases[:5]])
    assert any(c["case_id"] == case_id for c in cases)

    # 3. Submit supervisor approve decision
    dec_res = client.post(f"/ops/kyc/{case_id}/decision", json={
        "decision": "APPROVE",
        "reason": "Entity verified via state VAT/commercial tax portal",
        "actor": "supervisor@airtel.com",
    })
    assert dec_res.status_code == 200
    assert dec_res.json()["verdict"] == "PASS"

    # 4. Verify case status in DB
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    assert case.verdict == "PASS"


def test_ops_funnel_baseline_comparison(client):
    """Verifies conversion funnel metrics with empirical baseline comparison."""
    res = client.get("/ops/funnel")
    assert res.status_code == 200
    data = res.json()
    assert "baseline" in data
    assert data["baseline"]["conversion_pct"] == 7.4
    assert data["baseline"]["activation_days"] == 17.6
    assert data["baseline"]["status_chases"] == 3.0
    assert data["baseline"]["cac_inr"] == 15000

    assert "prototype" in data
    assert data["prototype"]["activation_days"] == 2.1
    assert data["prototype"]["status_chases"] == 0.0


def test_whatsapp_webhook_interactions(client, db):
    """Verifies inbound WhatsApp messages, plan requests, button replies, and outbox logging."""
    test_phone = "9822334455"

    # 1. Text enquiry for quote
    msg_res = client.post("/webhooks/whatsapp", json={
        "phone": test_phone,
        "text": "Hello, need high-speed office fiber plan quote",
    })
    assert msg_res.status_code == 200
    resp1 = msg_res.json()
    assert resp1["status"] == "DELIVERED"
    assert "Biz Fibre" in resp1["reply"]
    assert any(b["id"] == "ACCEPT_QUOTE" for b in resp1["buttons"])
    lead_id = resp1["lead_id"]

    # 2. Tap interactive button: ACCEPT_QUOTE
    btn_res = client.post("/webhooks/whatsapp", json={
        "phone": test_phone,
        "lead_id": lead_id,
        "button_id": "ACCEPT_QUOTE",
    })
    assert btn_res.status_code == 200
    resp2 = btn_res.json()
    assert "accepted" in resp2["reply"].lower()
    assert "sign" in resp2["reply"].lower()

    # 3. Simulate WhatsApp image document upload
    upload_res = client.post("/webhooks/whatsapp", json={
        "phone": test_phone,
        "lead_id": lead_id,
        "media_url": "https://storage.airtel.in/specimens/k01_gst.png",
    })
    assert upload_res.status_code == 200
    resp3 = upload_res.json()
    assert "Document Received" in resp3["reply"]

    # 4. Check outbox notifications logged in database
    outbox_res = client.get("/ops/outbox")
    assert outbox_res.status_code == 200
    notifs = outbox_res.json()
    assert any(n["channel"] == "WHATSAPP" for n in notifs)
