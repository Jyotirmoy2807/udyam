from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Lead, BusinessProfile, Quote, KycCase, KycDocument
from app.db.crypto import encrypt_identifier, mask_gstin
from app.ports import DefaultClock
from app.kyc.registries import DatabaseRegistry
from app.adapters.ocr_tesseract import TesseractExtractor
from app.kyc.consent import record_consent
from app.kyc.pipeline import evaluate_kyc_case

SPECIMEN_METADATA = {
    "K01": {"gstin": "37IHKXV5167L1ZS", "expected": "NEEDS_FIX", "reason": "Cancelled GSTIN & Blank Udyam Number"},
    "K02": {"gstin": "19EOGXH4115Y1ZL", "expected": "PASS", "reason": "Skewed certificate auto-deskewed and recovered"},
    "K03": {"gstin": "27XUIXG0767D1ZP", "expected": "PASS", "reason": "Clean control specimen"},
    "K04": {"gstin": "08YJEXS5191A1ZM", "expected": "NEEDS_FIX", "reason": "Blurry certificate (Laplacian variance < 100)"},
    "K05": {"gstin": "36AAECR2040M1Z5", "expected": "NEEDS_FIX", "reason": "Missing required Udyam certificate"},
    "K06": {"gstin": "08YKZXS5189L1ZO", "expected": "PASS", "reason": "Saffron Unisex Salon exact GSTIN lookup avoids collision"},
    "K07": {"gstin": "07CPCXN0398P1ZT", "expected": "NEEDS_FIX", "reason": "Name mismatch (Shri Physio Clinic vs Neelgiri Physio Clinic)"},
    "K08": {"gstin": "24XORXG9365M1Z3", "expected": "PASS", "reason": "Clean specimen"},
    "K09": {"gstin": "37LDYXK0296F1ZB", "expected": "PASS", "reason": "Clean specimen"},
    "K10": {"gstin": "27QHJXK0658U1ZL", "expected": "PASS", "reason": "Clean specimen"},
    "K11": {"gstin": "03KGZXT1320R1ZZ", "expected": "NEEDS_FIX", "reason": "Stale address proof (257 days old > 90 days)"},
    "K12": {"gstin": "37NBLXS1145E1ZU", "expected": "PASS", "reason": "Clean specimen"},
}


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def extractor():
    return TesseractExtractor()


@pytest.fixture(scope="module")
def clock():
    return DefaultClock(datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc))


def find_specimen_dir() -> Path:
    candidates = [
        Path("data/kyc_documents"),
        Path("../data/kyc_documents"),
        Path("data/YTL_TrackA_Udyam_Digital_Data/kyc_documents"),
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "kyc_documents",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not find data/kyc_documents directory")


@pytest.mark.parametrize("app_id", [f"K{i:02d}" for i in range(1, 13)])
def test_specimen_applicant_kyc_verdict(db_session: Session, extractor, clock, app_id: str):
    """Evaluates each of the 12 specimen applicants (K01-K12) and verifies exact expected verdict."""
    specimen_dir = find_specimen_dir()
    meta = SPECIMEN_METADATA[app_id]
    entered_gstin = meta["gstin"]
    expected_verdict = meta["expected"]

    # 1. Create Lead and Profile
    lead = Lead(
        id=uuid4(),
        source="kyc_test_suite",
        language="en",
        phone_masked="******3210",
        status="NEW",
    )
    db_session.add(lead)

    bp = BusinessProfile(
        lead_id=lead.id,
        business_type="Enterprise",
        segment="micro",
        city="Delhi",
        tier=1,
        employees=10,
        sites=1,
        has_gstin=True,
    )
    db_session.add(bp)
    db_session.commit()

    # 2. Record explicit consent (DPDP Act gate)
    consent = record_consent(
        session=db_session,
        lead_id=lead.id,
        purposes=["kyc_verification", "service_activation"],
        language="en",
    )

    # 3. Create Quote requiring GST
    quote = Quote(
        id=uuid4(),
        lead_id=lead.id,
        version=1,
        term_months=12,
        monthly_recurring=2500,
        one_time=0,
        first_month_total=2500,
        status="ACCEPTED",
    )
    db_session.add(quote)
    db_session.flush()

    # 4. Create KycCase
    case = KycCase(
        id=uuid4(),
        lead_id=lead.id,
        quote_id=quote.id,
        consent_id=consent.id,
        gstin_enc=encrypt_identifier(entered_gstin),
        gstin_masked=mask_gstin(entered_gstin),
        verdict="PENDING",
    )
    db_session.add(case)
    db_session.flush()

    # 5. Extract and attach all available document slots
    slots = ["address_proof", "gst_certificate", "signatory_id", "udyam_certificate"]
    for slot in slots:
        img_file = specimen_dir / f"{app_id}_{slot}.png"
        if not img_file.exists():
            continue  # e.g. K05 missing udyam_certificate

        with open(img_file, "rb") as f:
            img_bytes = f.read()

        extraction = extractor.extract_document(img_bytes, slot)

        doc = KycDocument(
            id=uuid4(),
            case_id=case.id,
            slot=slot,
            storage_key=f"kyc/{case.id}/{slot}.png",
            sha256="test_sha256",
            quality={
                "laplacian_variance": extraction.quality.laplacian_variance,
                "is_blurry": extraction.quality.is_blurry,
                "skew_angle": extraction.quality.skew_angle,
                "is_skewed": extraction.quality.is_skewed,
                "watermark_detected": extraction.quality.watermark_detected,
            },
            extracted=extraction.extracted_fields,
            confidence=extraction.field_confidences,
            delete_after=clock.now() + timedelta(days=30),
        )
        db_session.add(doc)

    db_session.commit()

    # 6. Evaluate KYC Case
    registry = DatabaseRegistry(db_session)
    verdict, checks, fix_messages = evaluate_kyc_case(
        session=db_session,
        case_id=case.id,
        registry=registry,
        clock=clock,
    )

    print(f"\n[{app_id}] Expected: {expected_verdict} | Actual: {verdict}")
    if fix_messages:
        print(f"  Fix messages: {fix_messages}")

    assert verdict == expected_verdict, (
        f"Applicant {app_id} expected verdict {expected_verdict} ({meta['reason']}), got {verdict}. "
        f"Checks: {[(c.check_code, c.outcome) for c in checks]}"
    )
