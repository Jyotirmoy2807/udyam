from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
import re
from rapidfuzz import fuzz

from app.ports import GstinRecord, UdyamRecord, DefaultClock

_MOD36_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_valid(s: str) -> bool:
    """Validates 15-character GSTIN structure and Modulo-36 check digit."""
    if not s or len(s) != 15:
        return False
    s = s.upper()
    # Accept standard format with 4th PAN char as X or standard PAN letters
    if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$", s):
        return False

    t = 0
    for i, ch in enumerate(s[:14]):
        if ch not in _MOD36_CHARS:
            return False
        v = _MOD36_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        t += v // 36 + v % 36

    expected_check = _MOD36_CHARS[(36 - t % 36) % 36]
    return s[14] == expected_check


def split_legal_name(legal_name: str) -> tuple[str, str]:
    """Splits 'Owner (Prop. Business Name)' into (owner_part, business_part)."""
    if not legal_name:
        return "", ""
    m = re.match(r"^(.*?)\s*\(\s*(?:Prop\.?|Proprietor)\s*(.*?)\s*\)$", legal_name, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return legal_name.strip(), legal_name.strip()


def parse_document_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    cleaned = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


@dataclass
class CheckResult:
    check_code: str
    outcome: str  # PASS, FAIL, REVIEW, WARN
    detail: dict[str, Any] = field(default_factory=dict)
    fix_message: str | None = None


def check_gstin_status(gstin_record: GstinRecord | None, ocr_gstin: str | None = None) -> CheckResult:
    if not gstin_record:
        return CheckResult(
            check_code="GSTIN_NOT_FOUND",
            outcome="FAIL",
            detail={"message": "GSTIN not found in official mock registry"},
            fix_message="Please enter a valid, registered GSTIN.",
        )

    status = (gstin_record.status or "").strip().title()
    if status in ("Cancelled", "Suspended"):
        return CheckResult(
            check_code="BLOCKED_GSTIN",
            outcome="FAIL",
            detail={"status": status, "gstin": gstin_record.gstin},
            fix_message=f"GSTIN {gstin_record.gstin} is {status}. Please provide an Active GSTIN or proceed without GST benefits.",
        )

    # Check format and checksum
    if not gstin_checksum_valid(gstin_record.gstin):
        return CheckResult(
            check_code="INVALID_GSTIN_CHECKSUM",
            outcome="FAIL",
            detail={"gstin": gstin_record.gstin},
            fix_message="The GSTIN checksum digit is invalid.",
        )

    # Cross-check OCR if present
    if ocr_gstin:
        ocr_clean = ocr_gstin.strip().upper()
        reg_clean = gstin_record.gstin.strip().upper()
        dist = sum(1 for a, b in zip(ocr_clean, reg_clean) if a != b) + abs(len(ocr_clean) - len(reg_clean))
        if dist > 3:
            return CheckResult(
                check_code="GSTIN_OCR_MISMATCH",
                outcome="FAIL",
                detail={"ocr_gstin": ocr_clean, "reg_gstin": reg_clean, "distance": dist},
                fix_message="GSTIN on certificate does not match registered GSTIN.",
            )
        elif dist > 0:
            return CheckResult(
                check_code="GSTIN_OCR_WARN",
                outcome="WARN",
                detail={"ocr_gstin": ocr_clean, "reg_gstin": reg_clean, "distance": dist},
            )

    return CheckResult(check_code="GSTIN_VALID", outcome="PASS", detail={"status": status})


def check_udyam_certificate(udyam_record: UdyamRecord | None, cert_udyam_number: str | None) -> CheckResult:
    if not cert_udyam_number or not cert_udyam_number.strip():
        return CheckResult(
            check_code="UDYAM_NUMBER_BLANK",
            outcome="FAIL",
            detail={"message": "Udyam registration number is blank on certificate"},
            fix_message="Uploaded Udyam certificate is missing a valid Udyam Registration Number.",
        )

    cleaned = cert_udyam_number.strip().upper()
    if not re.match(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$", cleaned):
        return CheckResult(
            check_code="INVALID_UDYAM_FORMAT",
            outcome="FAIL",
            detail={"udyam": cleaned},
            fix_message="Udyam number does not match standard UDYAM-XX-00-XXXXXXX format.",
        )

    if not udyam_record:
        return CheckResult(
            check_code="UDYAM_NOT_FOUND",
            outcome="FAIL",
            detail={"udyam": cleaned},
            fix_message=f"Udyam number {cleaned} not found in official MSME registry.",
        )

    return CheckResult(
        check_code="UDYAM_VALID",
        outcome="PASS",
        detail={"udyam": cleaned, "enterprise_name": udyam_record.enterprise_name},
    )


def check_split_name_match(
    legal_name: str,
    trade_name: str,
    cert_trade_name: str | None = None,
    cert_legal_name: str | None = None,
) -> CheckResult:
    owner_part, biz_part = split_legal_name(legal_name)
    cert_owner, cert_biz = split_legal_name(cert_legal_name or legal_name)

    # Compare legal-name business part against certificate trade name and registry trade name
    score_trade = fuzz.token_sort_ratio(biz_part, trade_name)
    score_cert = fuzz.token_sort_ratio(cert_biz, trade_name)
    min_score = min(score_trade, score_cert)

    if cert_trade_name:
        score_cert_trade = fuzz.token_sort_ratio(cert_trade_name, trade_name)
        min_score = min(min_score, score_cert_trade)

    if min_score >= 90.0:
        return CheckResult(check_code="NAME_MATCH", outcome="PASS", detail={"similarity": min_score})
    elif min_score >= 85.0:
        return CheckResult(
            check_code="NAME_MATCH_REVIEW",
            outcome="REVIEW",
            detail={"similarity": min_score, "biz_part": biz_part, "trade_name": trade_name},
        )
    else:
        return CheckResult(
            check_code="NAME_MISMATCH",
            outcome="FAIL",
            detail={"similarity": min_score, "biz_part": biz_part, "trade_name": trade_name},
            fix_message=f"Business name mismatch: certificate name does not match registered trade name ({trade_name}).",
        )


def check_address_proof_age(bill_date_str: str | None, today: date | None = None) -> CheckResult:
    ref_today = today or date(2026, 7, 15)
    bill_date = parse_document_date(bill_date_str)

    if not bill_date:
        return CheckResult(
            check_code="ADDRESS_PROOF_DATE_UNREADABLE",
            outcome="REVIEW",
            detail={"date_str": bill_date_str},
        )

    age_days = (ref_today - bill_date).days
    if age_days > 90:
        return CheckResult(
            check_code="STALE_ADDRESS_PROOF",
            outcome="FAIL",
            detail={"bill_date": str(bill_date), "age_days": age_days, "limit_days": 90},
            fix_message=f"Address proof utility bill is {age_days} days old (> 90 days limit). Please upload a recent bill.",
        )

    return CheckResult(
        check_code="ADDRESS_PROOF_CURRENT",
        outcome="PASS",
        detail={"bill_date": str(bill_date), "age_days": age_days},
    )


def check_address_pincode_match(pincode_doc: str | None, pincode_reg: str | None) -> CheckResult:
    if not pincode_doc or not pincode_reg:
        return CheckResult(check_code="PINCODE_MISSING", outcome="REVIEW")

    clean_doc = re.sub(r"\D", "", pincode_doc)
    clean_reg = re.sub(r"\D", "", pincode_reg)

    if clean_doc == clean_reg and len(clean_doc) == 6:
        return CheckResult(check_code="PINCODE_MATCH", outcome="PASS")
    else:
        return CheckResult(
            check_code="PINCODE_MISMATCH",
            outcome="FAIL",
            detail={"doc_pincode": clean_doc, "reg_pincode": clean_reg},
            fix_message=f"Pincode mismatch: document ({clean_doc}) does not match registry ({clean_reg}).",
        )


def check_signatory_validity(
    signatory_name: str,
    legal_name: str,
    valid_till_str: str | None = None,
    designation: str | None = None,
    constitution: str | None = "Proprietorship",
    today: date | None = None,
) -> CheckResult:
    ref_today = today or date(2026, 7, 15)
    owner_part, _ = split_legal_name(legal_name)

    name_score = fuzz.token_sort_ratio(signatory_name, owner_part)
    if name_score < 80.0:
        return CheckResult(
            check_code="SIGNATORY_NAME_MISMATCH",
            outcome="FAIL",
            detail={"signatory_name": signatory_name, "owner_part": owner_part, "similarity": name_score},
            fix_message="Signatory name on ID does not match registered owner name.",
        )

    # Check ID expiration date if present
    if valid_till_str:
        valid_date = parse_document_date(valid_till_str)
        if valid_date and valid_date <= ref_today:
            return CheckResult(
                check_code="SIGNATORY_ID_EXPIRED",
                outcome="FAIL",
                detail={"valid_till": str(valid_date)},
                fix_message="Signatory ID has expired. Please upload a valid, unexpired ID proof.",
            )

    # Designation check: non-blocking WARN
    if constitution and "company" in constitution.lower() and designation in ("Owner", "Office admin"):
        return CheckResult(
            check_code="DESIGNATION_WARN",
            outcome="WARN",
            detail={"designation": designation, "constitution": constitution},
        )

    return CheckResult(check_code="SIGNATORY_VALID", outcome="PASS")


def compute_case_verdict(checks: list[CheckResult], missing_slots: list[str]) -> tuple[str, list[str]]:
    """Evaluates case verdict:
    Any FAIL -> NEEDS_FIX.
    Any missing required slot -> NEEDS_FIX.
    No FAIL and >= 1 REVIEW -> MANUAL_REVIEW.
    Otherwise -> PASS (WARN never blocks)."""
    fix_messages = []

    if missing_slots:
        for slot in missing_slots:
            fix_messages.append(f"Missing required document: please upload {slot.replace('_', ' ')}.")
        return "NEEDS_FIX", fix_messages

    has_fail = False
    has_review = False

    for c in checks:
        if c.outcome == "FAIL":
            has_fail = True
            if c.fix_message:
                fix_messages.append(c.fix_message)
        elif c.outcome == "REVIEW":
            has_review = True

    if has_fail:
        return "NEEDS_FIX", fix_messages
    if has_review:
        return "MANUAL_REVIEW", []
    return "PASS", []
