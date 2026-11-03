"""Order lifecycle state machine enforcing deterministic transitions and append-only events."""

from datetime import datetime, timezone, date
from uuid import UUID
from typing import Any
from sqlalchemy.orm import Session
from app.db.models import Order, OrderItem, Quote
from app.orders.eta import compute_order_eta
from app.adapters.notify_outbox import OutboxNotifier
from app import events


# Allowed State Transitions
ORDER_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"KYC_PENDING", "CANCELLED", "FAILED"},
    "KYC_PENDING": {"KYC_APPROVED", "NEEDS_FIX", "CANCELLED", "FAILED"},
    "NEEDS_FIX": {"KYC_PENDING", "CANCELLED"},
    "KYC_APPROVED": {"PROVISIONING", "CANCELLED", "FAILED"},
    "PROVISIONING": {"ACTIVE", "CANCELLED", "FAILED"},
    "ACTIVE": set(),     # Terminal success
    "CANCELLED": set(),  # Terminal cancel
    "FAILED": set(),     # Terminal failure
}


class InvalidOrderTransitionError(Exception):
    pass


class OrderStateMachine:
    """Manages order progression, SLA calculations, and side-effects."""

    def __init__(self, db: Session):
        self.db = db

    def create_order_from_quote(
        self,
        quote_id: UUID,
        city_tier: int = 1,
        start_date: date | None = None,
    ) -> Order:
        """Instantiates a new order from an agreed quote."""
        quote = self.db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise ValueError(f"Quote {quote_id} not found.")

        # Extract product lines from quote (handles QuoteLine models or dicts)
        product_lines = quote.lines or []
        product_ids = [
            getattr(line, "product_id", None) or (line.get("product_id") if isinstance(line, dict) else None)
            for line in product_lines
        ]
        product_ids = [p for p in product_ids if p]

        # Compute SLA ETA
        order_eta, item_etas = compute_order_eta(
            self.db,
            product_ids=product_ids,
            city_tier=city_tier,
            start_date=start_date or date(2026, 7, 15),
        )

        order = Order(
            lead_id=quote.lead_id,
            quote_id=quote.id,
            status="SUBMITTED",
            eta=order_eta,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(order)
        self.db.flush()

        for line in product_lines:
            pid = getattr(line, "product_id", None) or (line.get("product_id") if isinstance(line, dict) else None)
            qty = getattr(line, "qty", 1) or (line.get("qty", 1) if isinstance(line, dict) else 1)
            if not pid:
                continue
            item = OrderItem(
                order_id=order.order_id,
                product_id=pid,
                qty=qty,
                status="PENDING",
                eta=item_etas.get(pid, order_eta),
            )
            self.db.add(item)

        events.emit(
            session=self.db,
            type="ORDER_CREATED",
            lead_id=quote.lead_id,
            order_id=order.order_id,
            payload={
                "quote_id": str(quote.id),
                "eta": order.eta.isoformat() if order.eta else None,
                "items_count": len(product_lines),
            },
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def transition(
        self,
        order_id: UUID,
        target_status: str,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Order:
        """Transitions order to target status if allowed, emitting events and triggering handlers."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        current_status = order.status
        allowed = ORDER_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidOrderTransitionError(
                f"Cannot transition order {order_id} from {current_status} to {target_status}. Allowed: {sorted(list(allowed))}"
            )

        order.status = target_status
        now = datetime.now(timezone.utc)

        # Trigger side-effects based on target state
        if target_status == "KYC_APPROVED":
            order.kyc_approved_at = now

        elif target_status == "PROVISIONING":
            for item in order.items:
                item.status = "PROVISIONING"

        elif target_status == "ACTIVE":
            for item in order.items:
                item.status = "INSTALLED"
                item.installed_at = now

            # Emit Activation Notification via OutboxNotifier
            notifier = OutboxNotifier(self.db)
            notifier.send(
                lead_id=order.lead_id,
                channel="SMS",
                template="ORDER_ACTIVATED",
                body=f"Your Airtel Udyam Digital order {order.order_id} is now ACTIVE! Welcome to Airtel Business.",
            )

        elif target_status in ("CANCELLED", "FAILED"):
            for item in order.items:
                item.status = target_status

        evt_payload = {"from_status": current_status, "to_status": target_status}
        if reason:
            evt_payload["reason"] = reason
        if payload:
            evt_payload.update(payload)

        events.emit(
            session=self.db,
            type="ORDER_STATE_CHANGED",
            lead_id=order.lead_id,
            order_id=order.order_id,
            payload=evt_payload,
        )

        self.db.commit()
        self.db.refresh(order)
        return order
