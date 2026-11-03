from datetime import datetime, timezone, date
import uuid
from typing import Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    event,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    target_segments = Column(JSONB, nullable=False, default=list)
    unit = Column(String(50), nullable=False)
    price_min = Column(Integer, nullable=False)
    price_max = Column(Integer, nullable=False)
    setup_fee = Column(Integer, nullable=False, default=0)
    min_contract_months = Column(Integer, nullable=False, default=12)
    city_tier_availability = Column(JSONB, nullable=False, default=list)
    min_employees = Column(Integer, nullable=False, default=1)
    min_sites = Column(Integer, nullable=False, default=1)
    requires_gstin = Column(String(1), nullable=False, default="N")
    requires_one_of = Column(JSONB, nullable=False, default=list)
    typical_install_days = Column(Integer, nullable=False, default=7)


class GstinRegistry(Base):
    __tablename__ = "gstin_registry"

    gstin = Column(String(15), primary_key=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=False)
    constitution = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    city = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    address = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)  # Active, Cancelled, Suspended
    registration_date = Column(String(50), nullable=False)


class UdyamRegistry(Base):
    __tablename__ = "udyam_registry"

    udyam_number = Column(String(50), primary_key=True)
    enterprise_name = Column(String(255), nullable=False)
    enterprise_type = Column(String(50), nullable=False)
    major_activity = Column(String(100), nullable=False)
    nic_description = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=False)
    date_of_registration = Column(String(50), nullable=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, default="web")
    language = Column(String(20), nullable=False, default="en")
    phone_enc = Column(Text, nullable=True)
    phone_masked = Column(String(20), nullable=True)
    partner_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(50), nullable=False, default="NEW")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    profile = relationship("BusinessProfile", back_populates="lead", uselist=False, cascade="all, delete-orphan")
    quotes = relationship("Quote", back_populates="lead", cascade="all, delete-orphan")


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    business_type = Column(String(100), nullable=True)
    segment = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    tier = Column(Integer, nullable=True)
    employees = Column(Integer, nullable=False, default=1)
    sites = Column(Integer, nullable=False, default=1)
    has_gstin = Column(Boolean, nullable=False, default=False)
    current_internet = Column(String(100), nullable=True)
    current_provider = Column(String(100), nullable=True)
    monthly_spend = Column(Integer, nullable=True)
    needs = Column(JSONB, nullable=False, default=list)
    mobile_lines = Column(Integer, nullable=False, default=0)

    lead = relationship("Lead", back_populates="profile")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    state = Column(String(50), nullable=False, default="GREETING")
    lang = Column(String(20), nullable=False, default="en")
    question_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    tool_calls = Column(JSONB, nullable=True)
    lang = Column(String(20), nullable=False, default="en")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    conversation = relationship("Conversation", back_populates="messages")


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    term_months = Column(Integer, nullable=False, default=12)
    monthly_recurring = Column(Integer, nullable=False, default=0)
    one_time = Column(Integer, nullable=False, default=0)
    first_month_total = Column(Integer, nullable=False, default=0)
    savings_vs_current = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="DRAFT")  # DRAFT, ACCEPTED, SUPERSEDED, CANCELLED
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    lead = relationship("Lead", back_populates="quotes")
    lines = relationship("QuoteLine", back_populates="quote", cascade="all, delete-orphan")


class QuoteLine(Base):
    __tablename__ = "quote_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(10), ForeignKey("products.product_id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_price = Column(Integer, nullable=False)
    line_monthly = Column(Integer, nullable=False)
    setup = Column(Integer, nullable=False, default=0)
    reason_codes = Column(JSONB, nullable=False, default=list)

    quote = relationship("Quote", back_populates="lines")
    product = relationship("Product")


class Consent(Base):
    __tablename__ = "consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    purposes = Column(JSONB, nullable=False, default=list)
    notice_version = Column(String(20), nullable=False, default="1.0")
    language = Column(String(20), nullable=False, default="en")
    accepted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)


class KycCase(Base):
    __tablename__ = "kyc_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    consent_id = Column(UUID(as_uuid=True), ForeignKey("consents.id", ondelete="CASCADE"), nullable=False)
    gstin_enc = Column(Text, nullable=True)
    gstin_masked = Column(String(20), nullable=True)
    udyam_enc = Column(Text, nullable=True)
    udyam_masked = Column(String(30), nullable=True)
    verdict = Column(String(50), nullable=False, default="PENDING")  # PENDING, PASS, MANUAL_REVIEW, NEEDS_FIX
    decided_at = Column(DateTime(timezone=True), nullable=True)

    documents = relationship("KycDocument", back_populates="case", cascade="all, delete-orphan")
    checks = relationship("KycCheck", back_populates="case", cascade="all, delete-orphan")


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("kyc_cases.id", ondelete="CASCADE"), nullable=False)
    slot = Column(String(50), nullable=False)  # address_proof, signatory_id, udyam_certificate, gst_certificate
    storage_key = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    quality = Column(JSONB, nullable=False, default=dict)
    extracted = Column(JSONB, nullable=False, default=dict)
    confidence = Column(JSONB, nullable=False, default=dict)
    delete_after = Column(DateTime(timezone=True), nullable=False)

    case = relationship("KycCase", back_populates="documents")


class KycCheck(Base):
    __tablename__ = "kyc_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("kyc_cases.id", ondelete="CASCADE"), nullable=False)
    check_code = Column(String(50), nullable=False)
    outcome = Column(String(20), nullable=False)  # PASS, FAIL, REVIEW, WARN
    detail = Column(JSONB, nullable=False, default=dict)

    case = relationship("KycCase", back_populates="checks")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="QUOTE_ACCEPTED")
    kyc_approved_at = Column(DateTime(timezone=True), nullable=True)
    eta = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String(10), ForeignKey("products.product_id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="PENDING")
    eta = Column(Date, nullable=True)
    installed_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    lead_id = Column(UUID(as_uuid=True), nullable=True)
    order_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)


# Immutable Append-Only Event Listeners
@event.listens_for(Event, "before_update")
def _block_event_update(mapper: Any, connection: Any, target: Any) -> None:
    raise RuntimeError("Events are append-only. UPDATE is strictly forbidden on events table.")


@event.listens_for(Event, "before_delete")
def _block_event_delete(mapper: Any, connection: Any, target: Any) -> None:
    raise RuntimeError("Events are append-only. DELETE is strictly forbidden on events table.")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), nullable=False)
    template = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Partner(Base):
    __tablename__ = "partners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    cities = Column(JSONB, nullable=False, default=list)
    segments = Column(JSONB, nullable=False, default=list)


class LeadScore(Base):
    __tablename__ = "lead_scores"

    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score = Column(Integer, nullable=False)
    model_version = Column(String(50), nullable=False)
    top_factors = Column(JSONB, nullable=False, default=list)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    actor = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    target = Column(String(100), nullable=False)
    detail = Column(JSONB, nullable=False, default=dict)
