from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models import KycCase, KycDocument, KycCheck, Quote, QuoteLine, Product
from app.events import emit
from app.ports import RegistryPort, ExtractorPort, ClockPort
from app.kyc.validators import (
    check_gstin_status,
    check_udyam_certificate,
    check_split_name_match,
    check_address_proof_age,
    check_address_pincode_match,
    check_signatory_validity,
    compute_case_verdict,
    CheckResult,
)


def evaluate_kyc_case(
    session: Session,
    case_id: UUID,
    registry: RegistryPort,
    clock: ClockPort,
) -> tuple[str, list[CheckResult], list[str]]:
    """Evaluates the full KYC case against all deterministic rules and registry lookups."""
    case = session.query(KycCase).filter(KycCase.id == case_id).first()
    if not case:
        raise ValueError(f"KYC Case {case_id} not found")

    quote = session.query(Quote).filter(Quote.id == case.quote_id).first()

    # Determine required document slots
    required_slots = {"address_proof", "signatory_id", "udyam_certificate"}
    # Conditional slot: gst_certificate required if quote products require GST or case has GSTIN
    requires_gst = False
    if quote:
        for ql in quote.lines:
            prod = session.query(Product).filter(Product.product_id == ql.product_id).first()
            if prod and prod.requires_gstin == "Y":
                requires_gst = True
                break
    if requires_gst or case.gstin_masked or case.gstin_enc:
        required_slots.add("gst_certificate")

    # Check uploaded slots
    docs_by_slot: dict[str, KycDocument] = {d.slot: d for d in case.documents}
    missing_slots = [s for s in sorted(list(required_slots)) if s not in docs_by_slot]

    checks: list[CheckResult] = []

    # 1. Completeness Check
    if missing_slots:
        for slot in missing_slots:
            checks.append(CheckResult(
                check_code="REQUIRED_DOC_MISSING",
                outcome="FAIL",
                detail={"missing_slot": slot},
                fix_message=f"Missing required document: please upload {slot.replace('_', ' ')}.",
            ))

    # 2. Quality Gate on all uploaded documents
    for slot, doc in docs_by_slot.items():
        quality = doc.quality or {}
        if quality.get("is_blurry", False) or quality.get("laplacian_variance", 999.0) < 100.0:
            checks.append(CheckResult(
                check_code="BLURRY",
                outcome="FAIL",
                detail={"slot": slot, "laplacian_variance": quality.get("laplacian_variance")},
                fix_message=f"Uploaded {slot.replace('_', ' ')} is too blurry (Laplacian variance < 100). Please re-upload a clear copy.",
            ))

    # 3. Document Classification Check
    for slot, doc in docs_by_slot.items():
        doc_type = (doc.extracted or {}).get("document_type_detected")
        if doc_type and doc_type != slot and doc_type != "unknown":
            checks.append(CheckResult(
                check_code="WRONG_DOCUMENT",
                outcome="FAIL",
                detail={"slot": slot, "detected": doc_type},
                fix_message=f"Uploaded file for {slot} appears to be a {doc_type}.",
            ))

    # 4. GSTIN Registry & Format Validation
    gst_doc = docs_by_slot.get("gst_certificate")
    raw_gstin = None
    if gst_doc and gst_doc.extracted:
        raw_gstin = gst_doc.extracted.get("gstin")

    from app.db.crypto import decrypt_identifier
    lookup_gstin = raw_gstin or (decrypt_identifier(case.gstin_enc) if case.gstin_enc else None)

    gstin_rec = None
    if lookup_gstin:
        gstin_rec = registry.get_gstin(lookup_gstin)
        checks.append(check_gstin_status(gstin_rec, ocr_gstin=raw_gstin))
    elif "gst_certificate" in required_slots:
        checks.append(CheckResult(
            check_code="GSTIN_NOT_ENTERED",
            outcome="FAIL",
            fix_message="GSTIN could not be identified on the certificate.",
        ))

    # 5. Udyam Registry & Format Validation
    udyam_doc = docs_by_slot.get("udyam_certificate")
    if udyam_doc and udyam_doc.extracted:
        cert_udyam_no = udyam_doc.extracted.get("udyam_number")
        udyam_rec = registry.get_udyam(cert_udyam_no) if cert_udyam_no else None
        checks.append(check_udyam_certificate(udyam_rec, cert_udyam_no))

    # 6. Split Name Matching
    if gstin_rec:
        cert_trade = gst_doc.extracted.get("trade_name") if gst_doc and gst_doc.extracted else None
        cert_legal = gst_doc.extracted.get("legal_name") if gst_doc and gst_doc.extracted else None
        checks.append(check_split_name_match(
            legal_name=gstin_rec.legal_name,
            trade_name=gstin_rec.trade_name,
            cert_trade_name=cert_trade,
            cert_legal_name=cert_legal,
        ))

    # 7. Address & Pincode Match
    addr_doc = docs_by_slot.get("address_proof")
    if addr_doc and addr_doc.extracted and gstin_rec:
        doc_pincode = addr_doc.extracted.get("pincode")
        checks.append(check_address_pincode_match(doc_pincode, gstin_rec.pincode))

    # 8. Address Proof Age Check (<= 90 days)
    if addr_doc and addr_doc.extracted:
        bill_date_str = addr_doc.extracted.get("bill_date")
        checks.append(check_address_proof_age(bill_date_str, today=clock.today()))

    # 9. Signatory & ID Validity
    sig_doc = docs_by_slot.get("signatory_id")
    if sig_doc and sig_doc.extracted and gstin_rec:
        sig_name = sig_doc.extracted.get("signatory_name", "")
        valid_till = sig_doc.extracted.get("valid_till")
        checks.append(check_signatory_validity(
            signatory_name=sig_name,
            legal_name=gstin_rec.legal_name,
            valid_till_str=valid_till,
            constitution=gstin_rec.constitution,
            today=clock.today(),
        ))

    # Compute Case Verdict
    verdict, fix_messages = compute_case_verdict(checks, missing_slots)

    # Persist checks
    session.query(KycCheck).filter(KycCheck.case_id == case.id).delete()
    for c in checks:
        kc = KycCheck(
            case_id=case.id,
            check_code=c.check_code,
            outcome=c.outcome,
            detail=c.detail,
        )
        session.add(kc)

    case.verdict = verdict
    case.decided_at = datetime.now(timezone.utc)

    emit(
        session=session,
        type=f"KYC_{verdict}",
        lead_id=case.lead_id,
        payload={
            "case_id": str(case.id),
            "verdict": verdict,
            "fix_messages": fix_messages,
        },
    )
    session.commit()
    return verdict, checks, fix_messages
