import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
import structlog

from app.db.session import SessionLocal
from app.db.models import GstinRegistry, Event
from app.kyc.registries import DatabaseRegistry
from app.events import emit
from app.db.crypto import (
    encrypt_identifier,
    decrypt_identifier,
    mask_gstin,
    mask_udyam,
    mask_phone,
    pii_mask_processor,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_gstin_lookup_by_exact_key_and_saffron_collision(db_session: Session):
    """Verifies that lookup by exact GSTIN key returns exact unique records,
    while searching trade name 'Saffron Unisex Salon' demonstrates 6 distinct rows (1 Suspended)."""
    registry = DatabaseRegistry(db_session)

    # 1. Verify exact key lookup works
    rec = registry.get_gstin("08YKZXS5189L1ZO")
    assert rec is not None
    assert rec.gstin == "08YKZXS5189L1ZO"
    assert rec.trade_name == "Saffron Unisex Salon"
    assert rec.status == "Active"
    assert rec.state == "Rajasthan"

    # 2. Check the suspended row by exact key
    suspended_rec = registry.get_gstin("03ODMXS1407Q1ZD")
    assert suspended_rec is not None
    assert suspended_rec.gstin == "03ODMXS1407Q1ZD"
    assert suspended_rec.trade_name == "Saffron Unisex Salon"
    assert suspended_rec.status == "Suspended"
    assert suspended_rec.state == "Punjab"

    # 3. Check all 6 collision rows in DB for Saffron Unisex Salon
    all_saffron = (
        db_session.query(GstinRegistry)
        .filter(GstinRegistry.trade_name == "Saffron Unisex Salon")
        .all()
    )
    assert len(all_saffron) == 6
    statuses = [r.status for r in all_saffron]
    assert statuses.count("Active") == 5
    assert statuses.count("Suspended") == 1


def test_events_table_is_strictly_append_only(db_session: Session):
    """Verifies that the events table allows inserts but rejects UPDATE and DELETE."""
    test_id = uuid4()
    evt = emit(
        session=db_session,
        type="TEST_EVENT_CREATED",
        lead_id=test_id,
        payload={"message": "Initial test payload"},
    )
    db_session.commit()

    # Attempt UPDATE -> Must raise RuntimeError
    evt.type = "TEST_EVENT_UPDATED"
    with pytest.raises(RuntimeError, match="Events are append-only. UPDATE is strictly forbidden"):
        db_session.commit()

    db_session.rollback()

    # Attempt DELETE -> Must raise RuntimeError
    saved_evt = db_session.query(Event).filter(Event.lead_id == test_id).first()
    assert saved_evt is not None
    db_session.delete(saved_evt)
    with pytest.raises(RuntimeError, match="Events are append-only. DELETE is strictly forbidden"):
        db_session.commit()

    db_session.rollback()


def test_fernet_encryption_and_masking():
    """Verifies Fernet encrypt/decrypt and masking functions."""
    gstin = "07IWUXS4825R1ZM"
    phone = "9876543210"
    udyam = "UDYAM-KL-00-3078801"

    # Encrypt / Decrypt
    enc_gstin = encrypt_identifier(gstin)
    assert enc_gstin != gstin
    assert decrypt_identifier(enc_gstin) == gstin

    enc_phone = encrypt_identifier(phone)
    assert enc_phone != phone
    assert decrypt_identifier(enc_phone) == phone

    # Masking
    assert mask_gstin(gstin) == "07**********1ZM"
    assert mask_phone(phone) == "******3210"
    assert mask_udyam(udyam) == "UDYAM-**-**-****801"


def test_structlog_pii_masking_processor():
    """Verifies that structlog processor masks GSTIN, Udyam, and phone numbers from log events."""
    raw_event = {
        "event": "Customer submitted onboarding request",
        "gstin": "07IWUXS4825R1ZM",
        "phone": "+919876543210",
        "udyam": "UDYAM-DL-00-1234567",
        "nested": {
            "comment": "Owner phone is 9812345678 and GSTIN 08YKZXS5189L1ZO verified",
        },
    }

    masked = pii_mask_processor(None, "info", raw_event)

    # Direct keys
    assert masked["gstin"] == "07**********1ZM"
    assert masked["phone"] == "******3210"
    assert masked["udyam"] == "UDYAM-**-**-****567"

    # Nested string
    nested_comment = masked["nested"]["comment"]
    assert "9812345678" not in nested_comment
    assert "08YKZXS5189L1ZO" not in nested_comment
    assert "******5678" in nested_comment
    assert "08**********1ZO" in nested_comment
