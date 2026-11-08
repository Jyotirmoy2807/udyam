"""Deterministic simulation hooks for edge case testing and order operations."""

from datetime import timedelta, datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models import Order, OrderItem
from app.adapters.notify_outbox import OutboxNotifier
from app import events


class OrderSimulator:
    """Simulates real-world telco field fulfillment exceptions and automated resolutions."""

    def __init__(self, db: Session):
        self.db = db

    def simulate_site_not_feasible(
        self,
        order_id: UUID,
        failed_product_id: str = "P01",
        fallback_product_id: str = "P04",
    ) -> dict[str, str]:
        """Handles site infeasibility by proposing and executing an automated AirFiber swap."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        # Find target item
        item = (
            self.db.query(OrderItem)
            .filter(OrderItem.order_id == order_id, OrderItem.product_id == failed_product_id)
            .first()
        )
        if not item:
            raise ValueError(f"Product {failed_product_id} not found in order {order_id}.")

        # Swap product to AirFiber P04
        item.product_id = fallback_product_id
        item.status = "SWAPPED_FALLBACK"

        events.emit(
            session=self.db,
            type="SITE_NOT_FEASIBLE_SWAP_EXECUTED",
            lead_id=order.lead_id,
            order_id=order.order_id,
            payload={
                "original_product": failed_product_id,
                "fallback_product": fallback_product_id,
                "reason": "Physical fiber unfeasible at premises; auto-swapped to 5G AirFiber",
            },
        )

        notifier = OutboxNotifier(self.db)
        notifier.send(
            lead_id=order.lead_id,
            channel="SMS",
            template="SWAP_NOTIFICATION",
            body=(
                f"Accel Update: Fiber is currently unfeasible at your location. "
                f"We have seamlessly updated your connection to high-speed 5G AirFiber ({fallback_product_id}) at no extra cost."
            ),
        )

        self.db.commit()
        return {
            "status": "SWAPPED",
            "from_product": failed_product_id,
            "to_product": fallback_product_id,
            "message": "Fiber unfeasible. Successfully swapped to AirFiber P04.",
        }

    def simulate_install_delayed(
        self,
        order_id: UUID,
        delay_days: int = 3,
        reason: str = "Awaiting municipal permissions for last-mile trenching",
    ) -> dict[str, str]:
        """Simulates last-mile delay, extending SLA ETA and notifying customer."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        if order.eta:
            order.eta = order.eta + timedelta(days=delay_days)

        for item in order.items:
            if item.eta:
                item.eta = item.eta + timedelta(days=delay_days)

        events.emit(
            session=self.db,
            type="INSTALLATION_DELAYED",
            lead_id=order.lead_id,
            order_id=order.order_id,
            payload={
                "delay_days": delay_days,
                "new_eta": order.eta.isoformat() if order.eta else None,
                "reason": reason,
            },
        )

        notifier = OutboxNotifier(self.db)
        notifier.send(
            lead_id=order.lead_id,
            channel="SMS",
            template="DELAY_NOTIFICATION",
            body=(
                f"Accel Update: Your installation has been rescheduled due to '{reason}'. "
                f"New estimated delivery date: {order.eta}."
            ),
        )

        self.db.commit()
        return {
            "status": "DELAYED",
            "new_eta": order.eta.isoformat() if order.eta else None,
            "delay_days": str(delay_days),
        }

    def simulate_payment_failure(
        self,
        order_id: UUID,
        reason: str = "Insufficient funds in bank account for mandate debit",
    ) -> dict[str, str]:
        """Simulates mandate execution failure, prompting retry workflow."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        events.emit(
            session=self.db,
            type="PAYMENT_FAILED_RETRY_SCHEDULED",
            lead_id=order.lead_id,
            order_id=order.order_id,
            payload={
                "reason": reason,
                "retry_attempt": 1,
                "action": "Triggering instant payment link via SMS",
            },
        )

        notifier = OutboxNotifier(self.db)
        notifier.send(
            lead_id=order.lead_id,
            channel="SMS",
            template="PAYMENT_RETRY",
            body=f"Accel Alert: Auto-debit failed for order {order_id} ({reason}). Please use the link sent to complete payment.",
        )

        self.db.commit()
        return {
            "status": "PAYMENT_FAILED_RETRYING",
            "reason": reason,
            "action": "SMS notification sent with retry payment link",
        }
