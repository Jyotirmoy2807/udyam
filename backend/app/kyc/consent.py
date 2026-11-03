from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.db.models import Consent
from app.events import emit

PRIVACY_NOTICES = {
    "1.0": {
        "en": {
            "title": "Airtel Business KYC & Service Activation Privacy Notice",
            "purposes": {
                "kyc_verification": "Collection and verification of business identification and signatory proofs against statutory registries (GSTIN, Udyam) for telecom compliance.",
                "service_activation": "Automated order provisioning, enterprise billing, and field feasibility survey.",
            },
            "retention": "KYC document scans are permanently purged within 30 days of verification.",
        },
        "hi": {
            "title": "एयरटेल बिजनेस केवाईसी और सेवा सक्रियण गोपनीयता सूचना",
            "purposes": {
                "kyc_verification": "दूरसंचार अनुपालन के लिए वैधानिक रजिस्ट्रियों (जीएसटीआईएन, उद्यम) के साथ व्यावसायिक पहचान और हस्ताक्षरकर्ता प्रमाणपत्रों का सत्यापन।",
                "service_activation": "स्वचालित सेवा सक्रियण, बिलिंग और फील्ड सर्वेक्षण।",
            },
            "retention": "सत्यापन के 30 दिनों के भीतर केवाईसी दस्तावेज़ स्थायी रूप से हटा दिए जाते हैं।",
        },
    }
}


def get_privacy_notice(lang: str = "en", version: str = "1.0") -> dict:
    ver_notices = PRIVACY_NOTICES.get(version, PRIVACY_NOTICES["1.0"])
    return ver_notices.get(lang, ver_notices["en"])


def record_consent(
    session: Session,
    lead_id: UUID,
    purposes: list[str],
    language: str = "en",
    notice_version: str = "1.0",
) -> Consent:
    """Records an explicit, immutable consent record under DPDP Act."""
    consent = Consent(
        lead_id=lead_id,
        purposes=purposes,
        language=language,
        notice_version=notice_version,
        accepted_at=datetime.now(timezone.utc),
    )
    session.add(consent)
    session.flush()

    emit(
        session=session,
        type="CONSENT_RECORDED",
        lead_id=lead_id,
        payload={
            "consent_id": str(consent.id),
            "purposes": purposes,
            "notice_version": notice_version,
            "language": language,
        },
    )
    session.commit()
    return consent


def verify_active_consent(session: Session, lead_id: UUID) -> Consent:
    """Verifies that the lead has an active, non-withdrawn consent record. Raises 403 if absent."""
    consent = (
        session.query(Consent)
        .filter(
            Consent.lead_id == lead_id,
            Consent.withdrawn_at.is_(None),
        )
        .order_by(Consent.accepted_at.desc())
        .first()
    )
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CONSENT_REQUIRED: Customer must provide explicit KYC consent before document upload or verification.",
        )
    return consent


def withdraw_consent(session: Session, consent_id: UUID) -> Consent:
    """Withdraws consent and schedules document purging."""
    consent = session.query(Consent).filter(Consent.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found")

    consent.withdrawn_at = datetime.now(timezone.utc)
    emit(
        session=session,
        type="CONSENT_WITHDRAWN",
        lead_id=consent.lead_id,
        payload={"consent_id": str(consent.id)},
    )
    session.commit()
    return consent
