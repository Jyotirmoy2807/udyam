"""Order lifecycle management, ETA computation, and failure simulation endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Order
from app.orders.state_machine import OrderStateMachine, InvalidOrderTransitionError
from app.orders.simulator import OrderSimulator

router = APIRouter(prefix="/orders", tags=["Orders & Provisioning"])


class CreateOrderRequest(BaseModel):
    quote_id: UUID
    city_tier: int = Field(default=1)


class TransitionOrderRequest(BaseModel):
    target_status: str
    reason: str | None = None


class SimulateDelayRequest(BaseModel):
    delay_days: int = 3
    reason: str = "Trenching permission delay"


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    """Creates a new order from an agreed quote and computes SLA ETAs."""
    sm = OrderStateMachine(db)
    order = sm.create_order_from_quote(req.quote_id, city_tier=req.city_tier)
    return {
        "order_id": order.order_id,
        "lead_id": order.lead_id,
        "quote_id": order.quote_id,
        "status": order.status,
        "eta": order.eta.isoformat() if order.eta else None,
        "items": [
            {
                "product_id": item.product_id,
                "qty": item.qty,
                "status": item.status,
                "eta": item.eta.isoformat() if item.eta else None,
            }
            for item in order.items
        ],
    }


@router.get("/{order_id}")
def get_order(order_id: UUID, db: Session = Depends(get_db)):
    """Retrieves full order status, SLA ETA, and individual item progress."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    return {
        "order_id": order.order_id,
        "lead_id": order.lead_id,
        "quote_id": order.quote_id,
        "status": order.status,
        "eta": order.eta.isoformat() if order.eta else None,
        "kyc_approved_at": order.kyc_approved_at.isoformat() if order.kyc_approved_at else None,
        "items": [
            {
                "product_id": item.product_id,
                "qty": item.qty,
                "status": item.status,
                "eta": item.eta.isoformat() if item.eta else None,
                "installed_at": item.installed_at.isoformat() if item.installed_at else None,
            }
            for item in order.items
        ],
    }


@router.post("/{order_id}/transition")
def transition_order_state(order_id: UUID, req: TransitionOrderRequest, db: Session = Depends(get_db)):
    """Transitions order status through the strict state machine."""
    sm = OrderStateMachine(db)
    try:
        updated = sm.transition(order_id, req.target_status, reason=req.reason)
        return {
            "order_id": updated.order_id,
            "status": updated.status,
            "kyc_approved_at": updated.kyc_approved_at.isoformat() if updated.kyc_approved_at else None,
        }
    except InvalidOrderTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/simulate/site-not-feasible")
def simulate_site_not_feasible(order_id: UUID, failed_product: str = "P01", fallback_product: str = "P04", db: Session = Depends(get_db)):
    """Simulates fiber infeasibility at customer site and auto-swaps to 5G AirFiber."""
    sim = OrderSimulator(db)
    return sim.simulate_site_not_feasible(order_id, failed_product, fallback_product)


@router.post("/{order_id}/simulate/install-delayed")
def simulate_install_delayed(order_id: UUID, req: SimulateDelayRequest, db: Session = Depends(get_db)):
    """Simulates installation delay and recalculates ETA."""
    sim = OrderSimulator(db)
    return sim.simulate_install_delayed(order_id, req.delay_days, req.reason)


@router.post("/{order_id}/simulate/payment-failed")
def simulate_payment_failed(order_id: UUID, reason: str = "Mandate debit failed", db: Session = Depends(get_db)):
    """Simulates recurring mandate payment failure."""
    sim = OrderSimulator(db)
    return sim.simulate_payment_failure(order_id, reason)
