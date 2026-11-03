"""Order lifecycle management, ETA computation, and failure simulation endpoints."""

import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.db.models import Order, OrderItem
from app.orders.state_machine import OrderStateMachine, InvalidOrderTransitionError
from app.orders.simulator import OrderSimulator
from app import events

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

    # Record TRACKER_VIEWED event
    events.emit(
        session=db,
        type="TRACKER_VIEWED",
        lead_id=order.lead_id,
        order_id=order.order_id,
        payload={"status": order.status},
    )
    db.commit()

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


class OpsSimulateOrderRequest(BaseModel):
    action: str = Field(default="advance", description="advance | site_not_feasible | install_delayed | payment_failed")
    failed_product: str = "P01"
    fallback_product: str = "P04"
    delay_days: int = 3
    reason: str | None = None


@router.post("/{order_id}/simulate")
def simulate_order_action(order_id: UUID, req: OpsSimulateOrderRequest, db: Session = Depends(get_db)):
    """Unified order simulator endpoint used by both demo simulator controls and Ops."""
    sim = OrderSimulator(db)
    if req.action == "site_not_feasible":
        return sim.simulate_site_not_feasible(order_id, req.failed_product, req.fallback_product)
    elif req.action == "install_delayed":
        return sim.simulate_install_delayed(order_id, req.delay_days, req.reason or "Municipal permission delay")
    elif req.action == "payment_failed":
        return sim.simulate_payment_failure(order_id, req.reason or "Mandate debit failed")
    elif req.action == "advance":
        return advance_order_status(order_id, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown simulation action: {req.action}")


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


@router.post("/{order_id}/advance")
def advance_order_status(order_id: UUID, db: Session = Depends(get_db)):
    """Advances order to next logical state: SUBMITTED -> KYC_PENDING -> KYC_APPROVED -> PROVISIONING -> ACTIVE."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    progression = {
        "DRAFT": "SUBMITTED",
        "SUBMITTED": "KYC_PENDING",
        "KYC_PENDING": "KYC_APPROVED",
        "KYC_APPROVED": "PROVISIONING",
        "PROVISIONING": "ACTIVE",
    }
    next_status = progression.get(order.status)
    if not next_status:
        return {"order_id": order.order_id, "status": order.status, "message": "Order is already in terminal state."}

    sm = OrderStateMachine(db)
    updated = sm.transition(order_id, next_status, reason="Simulated operational milestone completed")
    return {"order_id": updated.order_id, "status": updated.status}


@router.post("/{order_id}/mark-infeasible")
def mark_site_infeasible(order_id: UUID, product_id: str = "P01", db: Session = Depends(get_db)):
    """Marks an item as SITE_NOT_FEASIBLE to trigger the frontend AirFiber swap proposal card."""
    item = db.query(OrderItem).filter(OrderItem.order_id == order_id, OrderItem.product_id == product_id).first()
    if not item:
        # Fallback to first item if P01 not found
        item = db.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="No items found for order")

    item.status = "SITE_NOT_FEASIBLE"
    db.commit()
    return {"order_id": order_id, "item_product": item.product_id, "status": item.status}


@router.post("/{order_id}/swap-airfiber")
def swap_to_airfiber(order_id: UUID, db: Session = Depends(get_db)):
    """Executes the proposed AirFiber swap, replacing infeasible wireline with 5G AirFiber."""
    sim = OrderSimulator(db)
    # Check if P01 exists or an infeasible item exists
    item = db.query(OrderItem).filter(OrderItem.order_id == order_id, OrderItem.status == "SITE_NOT_FEASIBLE").first()
    failed_prod = item.product_id if item else "P01"
    try:
        res = sim.simulate_site_not_feasible(order_id, failed_prod, "P04")
        return {"status": "SWAP_APPROVED", "detail": res}
    except Exception as e:
        # If P01 already swapped or not found, update directly
        if item:
            item.product_id = "P04"
            item.status = "SWAPPED_FALLBACK"
            db.commit()
            return {"status": "SWAP_APPROVED", "fallback_product": "P04"}
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/retry-mandate")
def retry_mandate(order_id: UUID, db: Session = Depends(get_db)):
    """Resolves payment failure and resumes provisioning."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # Resume provisioning if failed
    if order.status == "FAILED":
        order.status = "PROVISIONING"
        db.commit()
    return {"order_id": order_id, "status": order.status, "message": "UPI Autopay mandate re-authorized successfully"}


@router.get("/{order_id}/stream")
async def stream_order_updates(order_id: UUID):
    """Server-Sent Events (SSE) stream providing real-time status and ETA updates for an order."""
    async def event_generator():
        last_state = ""
        for _ in range(60): # 60 ticks (~2 minutes max per connection)
            db = SessionLocal()
            try:
                order = db.query(Order).filter(Order.order_id == order_id).first()
                if order:
                    payload = {
                        "order_id": str(order.order_id),
                        "lead_id": str(order.lead_id),
                        "quote_id": str(order.quote_id),
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
                    current_repr = json.dumps(payload, sort_keys=True)
                    if current_repr != last_state:
                        last_state = current_repr
                        yield f"event: order_update\ndata: {json.dumps(payload)}\n\n"
            finally:
                db.close()
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
