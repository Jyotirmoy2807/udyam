import re
from typing import Any
from cryptography.fernet import Fernet
from app.config import settings

_fernet_instance: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.FERNET_KEY.strip().encode()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_identifier(val: str | None) -> str | None:
    if not val:
        return None
    f = get_fernet()
    return f.encrypt(val.encode("utf-8")).decode("utf-8")


def decrypt_identifier(enc_val: str | None) -> str | None:
    if not enc_val:
        return None
    f = get_fernet()
    return f.decrypt(enc_val.encode("utf-8")).decode("utf-8")


def mask_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    s = gstin.strip()
    if len(s) == 15:
        return f"{s[:2]}**********{s[-3:]}"
    return s[:2] + "*" * max(0, len(s) - 4) + s[-2:]


def mask_udyam(udyam: str | None) -> str | None:
    if not udyam:
        return None
    s = udyam.strip()
    # Format: UDYAM-XX-00-XXXXXXX
    if s.startswith("UDYAM-") and len(s) >= 16:
        # Show UDYAM-**-**-**** and last 3 digits
        return f"UDYAM-**-**-****{s[-3:]}"
    return f"UDYAM-**-**-****{s[-3:]}" if len(s) > 3 else "UDYAM-***"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone.strip())
    if len(digits) >= 10:
        last4 = digits[-4:]
        return f"******{last4}"
    return "******"


_GSTIN_REGEX = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b")
_UDYAM_REGEX = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b")
_PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?|91[\-\s]?|0)?[6-9]\d{9}\b")


def pii_mask_processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redacts GSTIN, Udyam, and Indian mobile numbers across all event_dict values."""
    def _sanitize(value: Any) -> Any:
        if isinstance(value, str):
            # Mask GSTIN: 15 chars -> first 2 + ********** + last 3
            def _replace_gstin(m: re.Match) -> str:
                g = m.group(0)
                return f"{g[:2]}**********{g[-3:]}"

            value = _GSTIN_REGEX.sub(_replace_gstin, value)

            # Mask Udyam: UDYAM-XX-00-XXXXXXX -> UDYAM-**-**-****123
            def _replace_udyam(m: re.Match) -> str:
                g = m.group(0)
                return f"UDYAM-**-**-****{g[-3:]}"

            value = _UDYAM_REGEX.sub(_replace_udyam, value)

            # Mask Phone: Indian mobile numbers -> ******1234
            def _replace_phone(m: re.Match) -> str:
                g = m.group(0)
                digits = re.sub(r"\D", "", g)
                return f"******{digits[-4:]}"

            value = _PHONE_REGEX.sub(_replace_phone, value)
            return value
        elif isinstance(value, dict):
            return {k: _sanitize(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_sanitize(v) for v in value]
        elif isinstance(value, tuple):
            return tuple(_sanitize(v) for v in value)
        return value

    return {k: _sanitize(v) for k, v in event_dict.items()}
