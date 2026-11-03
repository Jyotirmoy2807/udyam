"""KYC consent, document ingestion, and verification router."""

from datetime import datetime, timezone, timedelta
import hashlib
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import KycCase, KycDocument, KycCheck, Consent
from app.kyc.consent import ConsentManager, ConsentRequiredException
from app.kyc.registries import PostgresRegistryAdapter
from app.kyc.pipeline import evaluate_kyc_case
from app.adapters.storage_minio import MinioStorageAdapter
from app.adapters.ocr_tesseract import TesseractExtractor
from app.config import settings
from app.db.crypto import mask_gstin, encrypt_field

router = APIRouter(prefix="/kyc", tags=["KYC & Onboarding Verification"])


class ConsentRequest(BaseModel):
    lead_id: UUID
    purpose: str = Field(default="KYC_VERIFICATION")
    language: str = Field(default="en")
    notice_version: str = Field(default="1.0")


class CreateCaseRequest(BaseModel):
    lead_id: UUID
    quote_id: UUID
    gstin: str | None = None
    udyam_number: str | None = None


class VerifyCaseRequest(BaseModel):
    case_id: UUID


@router.post("/consent", status_code=status.HTTP_201_CREATED)
def record_kyc_consent(req: ConsentRequest, db: Session = Depends(get_db)):
    """Records explicit DPDP Act 2023 consent before document upload."""
    mgr = ConsentManager(db)
    consent = mgr.record_consent(
        lead_id=req.lead_id,
        purposes=[req.purpose],
        language=req.language,
        notice_version=req.notice_version,
    )
    return {
        "status": "CONSENT_RECORDED",
        "consent_id": consent.id,
        "lead_id": consent.lead_id,
        "accepted_at": consent.accepted_at.isoformat(),
        "notice_version": consent.notice_version,
    }


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_kyc_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    """Initializes a new KYC case linked to an accepted quote and lead."""
    mgr = ConsentManager(db)
    if not mgr.has_active_consent(req.lead_id, "KYC_VERIFICATION"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DPDP Consent required before creating a KYC case. Call POST /kyc/consent first.",
        )

    # Get active consent
    consent = db.query(Consent).filter(Consent.lead_id == req.lead_id, Consent.withdrawn_at.is_(None)).first()

    case = KycCase(
        lead_id=req.lead_id,
        quote_id=req.quote_id,
        consent_id=consent.id,
        gstin_enc=encrypt_field(req.gstin) if req.gstin else None,
        gstin_masked=mask_gstin(req.gstin) if req.gstin else None,
        verdict="PENDING",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return {
        "case_id": case.id,
        "lead_id": case.lead_id,
        "quote_id": case.quote_id,
        "verdict": case.verdict,
        "gstin_masked": case.gstin_masked,
    }


@router.post("/upload")
async def upload_kyc_document(
    case_id: UUID = Form(...),
    slot: str = Form(..., description="gst_certificate, udyam_certificate, address_proof, signatory_id"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads document to MinIO, runs CV quality checks & OCR, and registers document."""
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found.")

    image_bytes = await file.read()
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    # Upload to MinIO
    storage = MinioStorageAdapter()
    storage_key = f"cases/{case_id}/{slot}_{sha256[:8]}.png"
    storage.put_bytes(storage_key, image_bytes, content_type="image/png")

    # Run CV OCR Pipeline
    extractor = TesseractExtractor()
    ocr_result = extractor.extract_document(image_bytes, slot=slot)
    quality_dict = (
        ocr_result.quality.__dict__
        if hasattr(ocr_result.quality, "__dict__")
        else dict(ocr_result.quality)
    )

    # Upsert KYC Document record
    doc = (
        db.query(KycDocument)
        .filter(KycDocument.case_id == case_id, KycDocument.slot == slot)
        .first()
    )
    if not doc:
        doc = KycDocument(
            case_id=case_id,
            slot=slot,
            storage_key=storage_key,
            sha256=sha256,
            quality=quality_dict,
            extracted=ocr_result.extracted_fields,
            confidence=ocr_result.field_confidences,
            delete_after=datetime.now(timezone.utc) + timedelta(days=settings.DOCUMENT_RETENTION_DAYS),
        )
        db.add(doc)
    else:
        doc.storage_key = storage_key
        doc.sha256 = sha256
        doc.quality = quality_dict
        doc.extracted = ocr_result.extracted_fields
        doc.confidence = ocr_result.field_confidences
        doc.delete_after = datetime.now(timezone.utc) + timedelta(days=settings.DOCUMENT_RETENTION_DAYS)

    # If GSTIN extracted and not set, update case
    if slot == "gst_certificate" and "gstin" in ocr_result.extracted_fields:
        g = ocr_result.extracted_fields["gstin"]
        if g and not case.gstin_masked:
            case.gstin_enc = encrypt_field(g)
            case.gstin_masked = mask_gstin(g)

    db.commit()

    return {
        "status": "UPLOADED",
        "case_id": case_id,
        "slot": slot,
        "quality": quality_dict,
        "extracted_fields": ocr_result.extracted_fields,
    }


@router.post("/verify")
def verify_kyc_case(req: VerifyCaseRequest, db: Session = Depends(get_db)):
    """Triggers deterministic KYC evaluation pipeline across all uploaded documents and registries."""
    case = db.query(KycCase).filter(KycCase.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found.")

    registry = PostgresRegistryAdapter(db)

    class FixedClock:
        def today(self):
            return datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc).date()
        def now(self):
            return datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)

    verdict, checks, fix_messages = evaluate_kyc_case(
        session=db,
        case_id=req.case_id,
        registry=registry,
        clock=FixedClock(),
    )

    return {
        "case_id": req.case_id,
        "verdict": verdict,
        "checks_passed": sum(1 for c in checks if c.outcome == "PASS"),
        "total_checks": len(checks),
        "fix_messages": fix_messages,
    }


@router.get("/cases/{case_id}")
def get_kyc_case(case_id: UUID, db: Session = Depends(get_db)):
    """Retrieves full KYC case state, checks, and presigned document URLs."""
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found.")

    storage = MinioStorageAdapter()
    docs = []
    for d in case.documents:
        url = storage.generate_presigned_url(d.storage_key, ttl_seconds=300)
        docs.append({
            "slot": d.slot,
            "quality": d.quality,
            "extracted": d.extracted,
            "view_url": url,
        })

    checks = [
        {"check_code": c.check_code, "outcome": c.outcome, "detail": c.detail}
        for c in case.checks
    ]

    return {
        "case_id": case.id,
        "lead_id": case.lead_id,
        "quote_id": case.quote_id,
        "verdict": case.verdict,
        "gstin_masked": case.gstin_masked,
        "documents": docs,
        "checks": checks,
    }


SPECIMEN_METADATA = {
    "K01": {"gstin": "37IHKXV5167L1ZS", "expected": "NEEDS_FIX", "label": "K01: Cancelled GSTIN & Blank Udyam"},
    "K02": {"gstin": "19EOGXH4115Y1ZL", "expected": "PASS", "label": "K02: Skewed Document (Auto-deskewed)"},
    "K03": {"gstin": "27XUIXG0767D1ZP", "expected": "PASS", "label": "K03: Clean Control Specimen"},
    "K04": {"gstin": "08YJEXS5191A1ZM", "expected": "NEEDS_FIX", "label": "K04: Blurry Document (< 100 Laplacian)"},
    "K05": {"gstin": "36AAECR2040M1Z5", "expected": "NEEDS_FIX", "label": "K05: Missing Required Udyam Certificate"},
    "K06": {"gstin": "08YKZXS5189L1ZO", "expected": "PASS", "label": "K06: Saffron Salon (Clean Collision-Free)"},
    "K07": {"gstin": "07CPCXN0398P1ZT", "expected": "NEEDS_FIX", "label": "K07: Entity Name Mismatch"},
    "K08": {"gstin": "24XORXG9365M1Z3", "expected": "PASS", "label": "K08: Clean Enterprise Specimen"},
    "K09": {"gstin": "37LDYXK0296F1ZB", "expected": "PASS", "label": "K09: Clean Micro Enterprise Specimen"},
    "K10": {"gstin": "27QHJXK0658U1ZL", "expected": "PASS", "label": "K10: Clean Retail Specimen"},
    "K11": {"gstin": "03KGZXT1320R1ZZ", "expected": "NEEDS_FIX", "label": "K11: Stale Utility Bill (> 90 Days)"},
    "K12": {"gstin": "37NBLXS1145E1ZU", "expected": "PASS", "label": "K12: Clean Multi-Site Specimen"},
}


@router.get("/specimens")
def api_list_specimens():
    """Lists available test specimens K01-K12 for live demo quick-loading."""
    return [{"code": k, **v} for k, v in SPECIMEN_METADATA.items()]


@router.post("/specimens/{code}/apply")
def api_apply_specimen(code: str, case_id: UUID, db: Session = Depends(get_db)):
    """Applies test specimen documents directly into a case to test OCR & verification."""
    if code not in SPECIMEN_METADATA:
        raise HTTPException(status_code=404, detail="Specimen not found")
    case = db.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="KYC case not found")

    meta = SPECIMEN_METADATA[code]
    gstin = meta["gstin"]
    case.gstin_enc = encrypt_field(gstin)
    case.gstin_masked = mask_gstin(gstin)

    doc_dir = Path("data/kyc_documents")
    if not doc_dir.exists():
        doc_dir = Path("../data/kyc_documents")

    slots = ["gst_certificate", "udyam_certificate", "address_proof", "signatory_id"]
    if code == "K05":
        slots = ["gst_certificate", "address_proof", "signatory_id"]

    storage = MinioStorageAdapter()
    extractor = TesseractExtractor()
    attached = []

    for slot in slots:
        file_path = doc_dir / f"{code}_{slot}.png"
        if file_path.exists():
            image_bytes = file_path.read_bytes()
            sha256 = hashlib.sha256(image_bytes).hexdigest()
            storage_key = f"cases/{case_id}/{slot}_{sha256[:8]}.png"
            storage.put_bytes(storage_key, image_bytes, content_type="image/png")

            ocr_res = extractor.extract_document(image_bytes, slot=slot)
            quality_dict = (
                ocr_res.quality.__dict__
                if hasattr(ocr_res.quality, "__dict__")
                else dict(ocr_res.quality)
            )

            doc = db.query(KycDocument).filter(KycDocument.case_id == case_id, KycDocument.slot == slot).first()
            if not doc:
                doc = KycDocument(
                    case_id=case_id,
                    slot=slot,
                    storage_key=storage_key,
                    sha256=sha256,
                    quality=quality_dict,
                    extracted=ocr_res.extracted_fields,
                    confidence=ocr_res.field_confidences,
                    delete_after=datetime.now(timezone.utc) + timedelta(days=settings.DOCUMENT_RETENTION_DAYS),
                )
                db.add(doc)
            else:
                doc.storage_key = storage_key
                doc.sha256 = sha256
                doc.quality = quality_dict
                doc.extracted = ocr_res.extracted_fields
                doc.confidence = ocr_res.field_confidences
                doc.delete_after = datetime.now(timezone.utc) + timedelta(days=settings.DOCUMENT_RETENTION_DAYS)
            attached.append(slot)

    db.commit()
    return {
        "status": "SPECIMEN_APPLIED",
        "code": code,
        "gstin": gstin,
        "attached_slots": attached,
    }


@router.get("/registry/gstin/{gstin}")
def api_lookup_gstin(gstin: str, db: Session = Depends(get_db)):
    """Looks up GSTIN strictly in the seeded Postgres sandbox registry."""
    reg = PostgresRegistryAdapter(db)
    record = reg.get_gstin(gstin)
    if not record:
        raise HTTPException(status_code=404, detail="GSTIN not found in sandbox registry")
    return {
        "gstin": record.gstin,
        "legal_name": record.legal_name,
        "trade_name": record.trade_name,
        "constitution": record.constitution,
        "state": record.state,
        "city": record.city,
        "pincode": record.pincode,
        "address": record.address,
        "status": record.status,
        "registration_date": str(record.registration_date) if record.registration_date else None,
    }


@router.get("/registry/udyam/{udyam_number}")
def api_lookup_udyam(udyam_number: str, db: Session = Depends(get_db)):
    """Looks up Udyam Number strictly in the seeded Postgres sandbox registry."""
    reg = PostgresRegistryAdapter(db)
    record = reg.get_udyam(udyam_number)
    if not record:
        raise HTTPException(status_code=404, detail="Udyam number not found in sandbox registry")
    return {
        "udyam_number": record.udyam_number,
        "enterprise_name": record.enterprise_name,
        "enterprise_type": record.enterprise_type,
        "major_activity": record.major_activity,
        "nic_description": record.nic_description,
        "city": record.city,
        "state": record.state,
        "date_of_registration": str(record.date_of_registration) if record.date_of_registration else None,
    }
