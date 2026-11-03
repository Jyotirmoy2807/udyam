from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models import Event


def emit(
    session: Session,
    type: str,
    lead_id: UUID | None = None,
    order_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Emits an immutable event to the append-only events log."""
    evt = Event(
        type=type,
        lead_id=lead_id,
        order_id=order_id,
        payload=payload or {},
        ts=datetime.now(timezone.utc),
    )
    session.add(evt)
    session.flush()
    return evt
