import os
import sys
import httpx

# Try live HTTP server first; fall back to in-process TestClient if server is not up
try:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=1.5) as probe:
        probe.get("/health")
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)
    print("Connecting to live backend server at http://127.0.0.1:8000...")
except Exception:
    sys.path.insert(0, os.path.abspath("backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    print("Testing via in-process FastAPI TestClient...")

with client:
    # 1. Create Lead and Quote
    lead_res = client.post("/leads", json={"phone": "9876543210", "language": "en", "source": "web"})
    lead_id = lead_res.json()["lead_id"]
    quote_res = client.post("/quotes", json={"lead_id": lead_id, "products": [{"product_id": "P01", "qty": 1}]})
    quote_id = quote_res.json()["quote_id"]

    # 2. Aadhaar e-Sign
    esign_req = client.post(f"/quotes/{quote_id}/esign", json={"signatory_name": "Rajesh Kumar", "signatory_phone": "9876543210"})
    assert esign_req.status_code == 200, esign_req.text
    esign_id = esign_req.json()["esign_id"]
    print("e-Sign requested:", esign_id)

    esign_comp = client.post(f"/esign/{esign_id}/complete")
    assert esign_comp.status_code == 200, esign_comp.text
    print("e-Sign completed:", esign_comp.json()["status"])

    # 3. Authorize Mandate
    mandate_res = client.post("/quotes/mandate", json={
        "quote_id": quote_id,
        "lead_id": lead_id,
        "vpa": "rajesh@okhdfcbank",
        "bank_name": "HDFC Bank",
    })
    assert mandate_res.status_code == 200, mandate_res.text
    print("Mandate authorized:", mandate_res.json()["mandate_id"])

    # 4. Create Order
    order_res = client.post("/orders", json={"quote_id": quote_id, "city_tier": 1})
    assert order_res.status_code == 201, order_res.text
    order = order_res.json()
    order_id = order["order_id"]
    print(f"Order created: {order_id}, status: {order['status']}, ETA: {order['eta']}")

    # 5. Advance order status
    adv1 = client.post(f"/orders/{order_id}/advance")
    assert adv1.status_code == 200, adv1.text
    print("Advanced status:", adv1.json()["status"])

    # 6. Simulate Site Infeasible
    infeas = client.post(f"/orders/{order_id}/mark-infeasible?product_id=P01")
    assert infeas.status_code == 200, infeas.text
    print("Marked infeasible:", infeas.json()["status"])

    # 7. Approve AirFiber Swap
    swap_res = client.post(f"/orders/{order_id}/swap-airfiber")
    assert swap_res.status_code == 200, swap_res.text
    print("AirFiber Swap approved:", swap_res.json())

    # 8. Check updated order items
    get_order = client.get(f"/orders/{order_id}")
    assert get_order.status_code == 200
    items = get_order.json()["items"]
    print("Order items after swap:", [(i["product_id"], i["status"]) for i in items])
    assert any(i["product_id"] == "P04" for i in items), "P04 AirFiber not found in swapped items!"

    # 9. Simulate Delay
    delay_res = client.post(f"/orders/{order_id}/simulate/install-delayed", json={"delay_days": 3, "reason": "Trenching delay"})
    assert delay_res.status_code == 200, delay_res.text
    print("Delay simulated, new ETA:", delay_res.json()["new_eta"])

    # 10. Simulate Payment Failure & Retry
    pay_fail = client.post(f"/orders/{order_id}/simulate/payment-failed")
    assert pay_fail.status_code == 200
    print("Payment failure simulated:", pay_fail.json()["status"])

    retry_res = client.post(f"/orders/{order_id}/retry-mandate")
    assert retry_res.status_code == 200
    print("Mandate retried:", retry_res.json()["message"])

    print("All Checkpoint 5 signing, mandate, order lifecycle, and exception workflows verified successfully!")
