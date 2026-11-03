from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class GstinRecord:
    gstin: str
    legal_name: str
    trade_name: str
    constitution: str
    state: str
    city: str | None
    pincode: str | None
    address: str
    status: str
    registration_date: str


@dataclass(frozen=True)
class UdyamRecord:
    udyam_number: str
    enterprise_name: str
    enterprise_type: str
    major_activity: str
    nic_description: str | None
    city: str | None
    state: str
    date_of_registration: str


@dataclass
class QualityMetrics:
    laplacian_variance: float
    is_blurry: bool
    skew_angle: float
    is_skewed: bool
    watermark_detected: bool
    dpi: int | None = None


@dataclass
class ExtractionResult:
    slot: str
    document_type_detected: str
    extracted_fields: dict[str, Any]
    field_confidences: dict[str, float]
    quality: QualityMetrics
    raw_text: str


@runtime_checkable
class ClockPort(Protocol):
    def now(self) -> datetime:
        """Returns current system datetime (default 2026-07-15T10:00:00Z)."""
        ...

    def today(self) -> date:
        """Returns current system date (default 2026-07-15)."""
        ...


class DefaultClock:
    def __init__(self, fixed_dt: datetime | None = None):
        if fixed_dt is None:
            self._fixed_dt = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        else:
            self._fixed_dt = fixed_dt

    def set_datetime(self, dt: datetime) -> None:
        self._fixed_dt = dt

    def now(self) -> datetime:
        return self._fixed_dt

    def today(self) -> date:
        return self._fixed_dt.date()


@runtime_checkable
class RegistryPort(Protocol):
    def get_gstin(self, gstin: str) -> GstinRecord | None:
        """Lookup GSTIN strictly by exact ID (15 chars). Never by name."""
        ...

    def get_udyam(self, udyam_no: str) -> UdyamRecord | None:
        """Lookup Udyam registration strictly by exact ID."""
        ...


@runtime_checkable
class ExtractorPort(Protocol):
    def extract_document(self, image_bytes: bytes, slot: str) -> ExtractionResult:
        """Runs quality gates, deskewing, watermark masking, and OCR field extraction."""
        ...


@runtime_checkable
class LlmPort(Protocol):
    async def run_advisor_turn(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_iterations: int = 4,
    ) -> dict[str, Any]:
        """Runs multi-turn tool calling with Groq Llama 3.3 70B."""
        ...

    async def extract_kyc_fields_vision(
        self, image_bytes: bytes, slot: str
    ) -> dict[str, Any]:
        """Vision-based fallback field extraction using Llama 4 Scout."""
        ...

    async def transcribe_audio(self, audio_bytes: bytes, lang_code: str = "en") -> str:
        """Speech-to-text fallback using Whisper large v3 turbo."""
        ...


@runtime_checkable
class StoragePort(Protocol):
    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        ...

    def get_bytes(self, key: str) -> bytes:
        ...

    def generate_presigned_url(self, key: str, ttl_seconds: int = 300) -> str:
        ...

    def delete_object(self, key: str) -> None:
        ...


@runtime_checkable
class NotifierPort(Protocol):
    def send(self, lead_id: UUID, channel: str, template: str, body: str) -> None:
        """Dispatches an outbound notification (WhatsApp, SMS, or mock outbox)."""
        ...
