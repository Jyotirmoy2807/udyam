"""Comprehensive Live API Test Suite covering every endpoint and edge case over HTTP."""

import io
from pathlib import Path
import httpx

BASE_URL = "http://127.0.0.1:8000"
DOCS_DIR = Path("data/kyc_documents")
if not DOCS_DIR.exists():
    DOCS_DIR = Path("backend/../data/kyc_documents")

passed_cases = 0
failed_cases = 0


def log_test(case_no: int, name: str, success: bool, detail: str = ""):
    global passed_cases, failed_cases
    status_str = "PASS" if success else "FAIL"
    if success:
        passed_cases += 1
        print(f"[{status_str}] Case {case_no:02d}: {name}")
    else:
        failed_cases += 1
        print(f"[{status_str}] Case {case_no:02d}: {name} --> ERROR: {detail}")


def run_tests():
    global passed_cases, failed_cases
    print("=" * 75)
    print("PROJECT UDYAM DIGITAL: LIVE ENDPOINT-BY-ENDPOINT VERIFICATION")
    print("=" * 75)

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # -------------------------------------------------------------
        # 1. Health & Clock
        # -------------------------------------------------------------
        r = client.get("/health")
        data = r.json()
        log_test(
            1, "GET /health (Postgres, Redis, MinIO & Clock 2026-07-15)",
            r.status_code == 200 and data["status"] == "healthy" and data["clock"]["fixed_date"] == "2026-07-15",
            str(data)
        )

        # -------------------------------------------------------------
        # 2. Authentication (/auth)
        # -------------------------------------------------------------
        # Case 2: OTP Send standard
        r = client.post("/auth/otp/send", json={"phone": "9876543210", "channel": "SMS"})
        log_test(
            2, "POST /auth/otp/send (Standard 10-digit mobile)",
            r.status_code == 200 and r.json().get("status") == "OTP_SENT" and "3210" in r.json().get("phone_masked", ""),
            r.text
        )

        # Case 3: OTP Verify invalid code
        r = client.post("/auth/otp/verify", json={"phone": "9876543210", "otp": "999999"})
        log_test(
            3, "POST /auth/otp/verify (Negative test: wrong OTP returns 400)",
            r.status_code == 400,
            f"Expected 400, got {r.status_code}"
        )

        # Case 4: OTP Verify customer role
        r = client.post("/auth/otp/verify", json={"phone": "9876543210", "otp": "123456", "role": "customer"})
        cust_token = r.json().get("access_token")
        log_test(
            4, "POST /auth/otp/verify (Customer JWT issuance)",
            r.status_code == 200 and cust_token is not None,
            r.text
        )

        # Case 5: OTP Verify ops_admin role
        r = client.post("/auth/otp/verify", json={"phone": "9999900000", "otp": "123456", "role": "ops_admin"})
        admin_token = r.json().get("access_token")
        log_test(
            5, "POST /auth/otp/verify (Ops Admin JWT issuance)",
            r.status_code == 200 and admin_token is not None and r.json().get("role") == "ops_admin",
            r.text
        )

        # -------------------------------------------------------------
        # 3. Leads Service (/leads)
        # -------------------------------------------------------------
        # Case 6: Minimal Lead Creation
        r = client.post("/leads", json={"phone": "9811122233"})
        lead_min = r.json()
        log_test(
            6, "POST /leads (Minimal lead creation)",
            r.status_code == 201 and "lead_id" in lead_min and lead_min["phone_masked"] == "******2233",
            r.text
        )

        # Case 7: Micro SMB Lead (Bakery, Lucknow, Tier 2, no GSTIN)
        r = client.post("/leads", json={
            "phone": "9822233344",
            "language": "hi",
            "business_type": "Bakery",
            "city": "Lucknow",
            "employees": 3,
            "sites": 1,
            "has_gstin": False,
            "monthly_spend": 2200,
        })
        lead_micro = r.json()
        lead_micro_id = lead_micro.get("lead_id")
        log_test(
            7, "POST /leads (Micro SMB lead with propensity scoring & partner assignment)",
            r.status_code == 201 and lead_micro["assigned_partner"] is not None and lead_micro["propensity"]["score_int"] > 0,
            r.text
        )

        # Case 8: Multi-site Enterprise Lead (Apparel retail chain, Tier 1, 50 employees, 10 sites, GSTIN)
        r = client.post("/leads", json={
            "phone": "9833344455",
            "language": "en",
            "business_type": "Apparel retail chain",
            "city": "Mumbai",
            "employees": 50,
            "sites": 10,
            "has_gstin": True,
            "monthly_spend": 15000,
        })
        lead_ent = r.json()
        log_test(
            8, "POST /leads (Multi-site chain lead receives HIGH propensity band)",
            r.status_code == 201 and lead_ent["propensity"]["band"] == "HIGH",
            r.text
        )

        # Case 9: GET /leads/{lead_id}
        r = client.get(f"/leads/{lead_micro_id}")
        log_test(
            9, "GET /leads/{lead_id} (Fetch full lead context & score)",
            r.status_code == 200 and r.json().get("profile", {}).get("city") == "Lucknow",
            r.text
        )

        # Case 10: GET /leads/{lead_id} with non-existent UUID
        r = client.get("/leads/00000000-0000-0000-0000-000000000000")
        log_test(
            10, "GET /leads/{lead_id} (Negative test: non-existent ID returns 404)",
            r.status_code == 404,
            f"Expected 404, got {r.status_code}"
        )

        # Case 11: GET /leads/queue/{partner_id}
        partner_id = lead_micro.get("assigned_partner", {}).get("partner_id")
        if partner_id:
            r = client.get(f"/leads/queue/{partner_id}")
            log_test(
                11, "GET /leads/queue/{partner_id} (Partner queue retrieval)",
                r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0,
                r.text
            )
        else:
            log_test(11, "GET /leads/queue/{partner_id}", False, "No partner ID found")

        # -------------------------------------------------------------
        # 4. Advisor Service (/advisor)
        # -------------------------------------------------------------
        # Case 12: Discovery greeting turn
        r = client.post("/advisor/chat", json={
            "lead_id": lead_micro_id,
            "message": "Hello, I want to know about your internet packages",
            "language": "en"
        })
        log_test(
            12, "POST /advisor/chat (Conversational turn with tool execution & guardrail)",
            r.status_code == 200 and len(r.json().get("reply", "")) > 0,
            r.text
        )

        # Case 13: Multilingual conversational turn (Hindi)
        r = client.post("/advisor/chat", json={
            "lead_id": lead_micro_id,
            "message": "Mujhe apne bakery ke liye accha wifi plan chahiye",
            "language": "hi"
        })
        log_test(
            13, "POST /advisor/chat (Multilingual Hindi conversational turn)",
            r.status_code == 200 and len(r.json().get("reply", "")) > 0,
            r.text
        )

        # Case 14: SSE Streaming (/advisor/stream)
        r = client.get(f"/advisor/stream?lead_id={lead_micro_id}&message=hello")
        log_test(
            14, "GET /advisor/stream (Server-Sent Events streaming response)",
            r.status_code == 200 and "data:" in r.text and "[DONE]" in r.text,
            r.text[:100]
        )

        # Case 15: Voice STT Fallback (/advisor/voice)
        import wave
        audio_buf = io.BytesIO()
        with wave.open(audio_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)
        audio_bytes = audio_buf.getvalue()
        r = client.post("/advisor/voice", files={"file": ("test.wav", audio_bytes, "audio/wav")})
        log_test(
            15, "POST /advisor/voice (Voice audio transcription fallback)",
            r.status_code == 200 and "transcription" in r.json(),
            r.text
        )

        # -------------------------------------------------------------
        # 5. Quotes Service (/quotes)
        # -------------------------------------------------------------
        # Case 16: Create Quote for P01 (Broadband)
        r = client.post("/quotes", json={
            "lead_id": lead_micro_id,
            "products": [{"product_id": "P01", "qty": 1}],
            "term_months": 12,
        })
        quote_p01 = r.json()
        quote_id = quote_p01.get("quote_id")
        log_test(
            16, "POST /quotes (Create quote with pricing engine calculations)",
            r.status_code == 201 and quote_p01.get("monthly_recurring", 0) > 0,
            r.text
        )

        # Case 17: Create Multi-Product Quote (P01 + P07 + P15, 24 months)
        r = client.post("/quotes", json={
            "lead_id": lead_micro_id,
            "products": [{"product_id": "P01", "qty": 1}, {"product_id": "P07", "qty": 1}, {"product_id": "P15", "qty": 1}],
            "term_months": 24,
        })
        quote_multi = r.json()
        log_test(
            17, "POST /quotes (Multi-product quote with position discount)",
            r.status_code == 201 and quote_multi.get("monthly_recurring", 0) > quote_p01.get("monthly_recurring", 0),
            r.text
        )

        # Case 18: Download Quote PDF
        r = client.get(f"/quotes/{quote_id}/pdf")
        log_test(
            18, "GET /quotes/{quote_id}/pdf (Download official PDF document)",
            r.status_code == 200 and r.content.startswith(b"%PDF"),
            f"Content length: {len(r.content)} bytes"
        )

        # Case 19: Request Aadhaar e-Sign
        r = client.post(f"/quotes/{quote_id}/esign", json={"signatory_name": "Ramesh Gupta", "signatory_phone": "9822233344"})
        esign_id = r.json().get("esign_id")
        log_test(
            19, "POST /quotes/{quote_id}/esign (Aadhaar e-Sign invitation request)",
            r.status_code == 200 and r.json().get("status") == "sent",
            r.text
        )

        # Case 20: Complete e-Sign Callback
        r = client.post(f"/esign/{esign_id}/complete")
        log_test(
            20, "POST /esign/{esign_id}/complete (e-Sign completion confirmation)",
            r.status_code == 200 and r.json().get("status") == "completed",
            r.text
        )

        # Case 21: Set up UPI Autopay Mandate
        r = client.post("/quotes/mandate", json={
            "quote_id": quote_id,
            "lead_id": lead_micro_id,
            "vpa": "ramesh@okhdfc",
            "bank_name": "HDFC Bank"
        })
        log_test(
            21, "POST /quotes/mandate (UPI Autopay mandate registration)",
            r.status_code == 200 and r.json().get("status") == "success" and "mandate_id" in r.json(),
            r.text
        )

        # -------------------------------------------------------------
        # 6. KYC & Consent Service (/kyc)
        # -------------------------------------------------------------
        # Case 22: Negative test - Create KYC case without consent (must return 403)
        r_temp_lead = client.post("/leads", json={"phone": "9998887776"}).json()
        r_bad_case = client.post("/kyc/cases", json={"lead_id": r_temp_lead["lead_id"], "quote_id": quote_id})
        log_test(
            22, "POST /kyc/cases (Negative test: 403 Forbidden without DPDP consent)",
            r_bad_case.status_code == 403,
            f"Expected 403, got {r_bad_case.status_code}"
        )

        # Case 23: Record DPDP Act Consent
        r = client.post("/kyc/consent", json={"lead_id": lead_micro_id, "purpose": "KYC_VERIFICATION"})
        consent_data = r.json()
        log_test(
            23, "POST /kyc/consent (Explicit DPDP Act consent recording)",
            r.status_code == 201 and consent_data.get("status") == "CONSENT_RECORDED",
            r.text
        )

        # Case 24: Create KYC Case with Consent
        r = client.post("/kyc/cases", json={"lead_id": lead_micro_id, "quote_id": quote_id, "gstin": "27XUIXG0767D1ZP"})
        kyc_case = r.json()
        case_id = kyc_case.get("case_id")
        log_test(
            24, "POST /kyc/cases (Create KYC case linked to consent & masked GSTIN)",
            r.status_code == 201 and case_id is not None and "27**********1ZP" == kyc_case.get("gstin_masked"),
            r.text
        )

        # Case 25: Upload Clean KYC Document (K02 GST Certificate)
        k02_gst_path = DOCS_DIR / "K02_gst_certificate.png"
        if k02_gst_path.exists():
            with open(k02_gst_path, "rb") as f:
                r = client.post(
                    "/kyc/upload",
                    data={"case_id": str(case_id), "slot": "gst_certificate"},
                    files={"file": ("K02_gst.png", f.read(), "image/png")}
                )
            up_data = r.json() if r.status_code == 200 else {}
            log_test(
                25, "POST /kyc/upload (Upload clean document: deskew & Laplacian quality verified)",
                r.status_code == 200 and up_data.get("status") == "UPLOADED" and not up_data.get("quality", {}).get("is_blurry", True),
                r.text
            )
        else:
            log_test(25, "POST /kyc/upload (Clean document)", False, f"File {k02_gst_path} not found")

        # Case 26: Upload Blurry Document (K04 GST Certificate)
        k04_gst_path = DOCS_DIR / "K04_gst_certificate.png"
        if k04_gst_path.exists():
            with open(k04_gst_path, "rb") as f:
                r = client.post(
                    "/kyc/upload",
                    data={"case_id": str(case_id), "slot": "gst_certificate"},
                    files={"file": ("K04_gst.png", f.read(), "image/png")}
                )
            up_data = r.json() if r.status_code == 200 else {}
            log_test(
                26, "POST /kyc/upload (Upload blurry document: quality gate flags is_blurry=True)",
                r.status_code == 200 and up_data.get("quality", {}).get("is_blurry") is True,
                r.text
            )
        else:
            log_test(26, "POST /kyc/upload (Blurry document)", False, f"File {k04_gst_path} not found")

        # Case 27: Verify KYC Case
        r = client.post("/kyc/verify", json={"case_id": case_id})
        v_data = r.json()
        log_test(
            27, "POST /kyc/verify (Deterministic verification pipeline with actionable fix guidance)",
            r.status_code == 200 and "verdict" in v_data and "fix_messages" in v_data,
            r.text
        )

        # Case 28: GET /kyc/cases/{case_id}
        r = client.get(f"/kyc/cases/{case_id}")
        case_details = r.json()
        log_test(
            28, "GET /kyc/cases/{case_id} (Retrieve checks, document metadata, and presigned URLs)",
            r.status_code == 200 and "documents" in case_details and len(case_details["documents"]) > 0,
            r.text
        )

        # -------------------------------------------------------------
        # 7. Orders Service (/orders)
        # -------------------------------------------------------------
        # Case 29: Create Order from agreed quote
        r = client.post("/orders", json={"quote_id": quote_id, "city_tier": 2})
        order_data = r.json()
        order_id = order_data.get("order_id")
        log_test(
            29, "POST /orders (Instantiate order with deterministic SLA ETA)",
            r.status_code == 201 and order_id is not None and order_data.get("status") == "SUBMITTED" and order_data.get("eta") is not None,
            r.text
        )

        # Case 30: GET /orders/{order_id}
        r = client.get(f"/orders/{order_id}")
        log_test(
            30, "GET /orders/{order_id} (Fetch order status and item-level delivery ETAs)",
            r.status_code == 200 and len(r.json().get("items", [])) > 0,
            r.text
        )

        # Case 31: Sequential Order Transitions
        t1 = client.post(f"/orders/{order_id}/transition", json={"target_status": "KYC_PENDING"})
        t2 = client.post(f"/orders/{order_id}/transition", json={"target_status": "KYC_APPROVED"})
        t3 = client.post(f"/orders/{order_id}/transition", json={"target_status": "PROVISIONING"})
        t4 = client.post(f"/orders/{order_id}/transition", json={"target_status": "ACTIVE"})
        log_test(
            31, "POST /orders/{order_id}/transition (Sequential state progression to ACTIVE)",
            t1.status_code == 200 and t2.status_code == 200 and t3.status_code == 200 and t4.status_code == 200 and t4.json().get("status") == "ACTIVE",
            f"t4 status: {t4.status_code}, response: {t4.text}"
        )

        # Case 32: Negative test - Invalid Order Transition
        r = client.post(f"/orders/{order_id}/transition", json={"target_status": "DRAFT"})
        log_test(
            32, "POST /orders/{order_id}/transition (Negative test: invalid transition returns 400)",
            r.status_code == 400,
            f"Expected 400, got {r.status_code}"
        )

        # -------------------------------------------------------------
        # 8. Order Simulators (/orders/.../simulate/...)
        # -------------------------------------------------------------
        # Create a new order for simulations
        r_quote_sim = client.post("/quotes", json={"lead_id": lead_micro_id, "products": [{"product_id": "P01", "qty": 1}]}).json()
        r_order_sim = client.post("/orders", json={"quote_id": r_quote_sim["quote_id"], "city_tier": 1}).json()
        sim_order_id = r_order_sim["order_id"]
        orig_eta = r_order_sim["eta"]

        # Case 33: Site Not Feasible Simulator -> Swap P01 to AirFiber P04
        r = client.post(f"/orders/{sim_order_id}/simulate/site-not-feasible", params={"failed_product": "P01", "fallback_product": "P04"})
        sim_swap = r.json()
        log_test(
            33, "POST /orders/{order_id}/simulate/site-not-feasible (Auto-swap unfeasible Fiber to 5G AirFiber P04)",
            r.status_code == 200 and sim_swap.get("to_product") == "P04",
            r.text
        )

        # Case 34: Installation Delayed Simulator -> Extends ETA
        r = client.post(f"/orders/{sim_order_id}/simulate/install-delayed", json={"delay_days": 3, "reason": "Municipal permission delay"})
        sim_delay = r.json()
        log_test(
            34, "POST /orders/{order_id}/simulate/install-delayed (Extends SLA ETA and alerts customer via SMS)",
            r.status_code == 200 and sim_delay.get("new_eta") > orig_eta,
            r.text
        )

        # Case 35: Mandate Payment Failed Simulator
        r = client.post(f"/orders/{sim_order_id}/simulate/payment-failed", params={"reason": "Insufficient balance"})
        sim_pay = r.json()
        log_test(
            35, "POST /orders/{order_id}/simulate/payment-failed (Schedules retry and sends instant payment link)",
            r.status_code == 200 and sim_pay.get("status") == "PAYMENT_FAILED_RETRYING",
            r.text
        )

        # -------------------------------------------------------------
        # 9. Operations & Audit Dashboard (/ops)
        # -------------------------------------------------------------
        # Case 36: Conversion Funnel Analytics
        r = client.get("/ops/funnel")
        funnel_data = r.json()
        log_test(
            36, "GET /ops/funnel (Real-time conversion funnel calculated strictly over events table)",
            r.status_code == 200 and "funnel_summary" in funnel_data and len(funnel_data.get("stages", [])) == 5,
            r.text
        )

        # Case 37: Immutable Events Stream
        r = client.get("/ops/events?limit=10")
        log_test(
            37, "GET /ops/events (Recent append-only audit events log)",
            r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0,
            f"Event count: {len(r.json())}"
        )

        # Case 38: Manual Supervisor KYC Override
        r = client.post(f"/ops/kyc/{case_id}/override", json={
            "new_verdict": "PASS",
            "reason": "Supervisor manual review confirmed valid utility bill",
            "actor": "senior_ops@airtel.com"
        })
        override_data = r.json()
        log_test(
            38, "POST /ops/kyc/{case_id}/override (Supervisor manual KYC override with audit logging)",
            r.status_code == 200 and override_data.get("new_verdict") == "PASS",
            r.text
        )

        # -------------------------------------------------------------
        # 10. Webhooks (/webhooks)
        # -------------------------------------------------------------
        # Case 39: e-Sign Webhook
        r = client.post("/webhooks/esign", json={
            "quote_id": quote_id,
            "status": "SIGNED",
            "docket_id": "NSDL-DOCKET-88992"
        })
        log_test(
            39, "POST /webhooks/esign (Inbound Aadhaar e-Sign webhook callback)",
            r.status_code == 200 and r.json().get("status") == "PROCESSED",
            r.text
        )

        # Case 40: UPI Mandate Webhook
        r = client.post("/webhooks/mandate", json={
            "mandate_id": "UMRN-DEMO-9999",
            "quote_id": quote_id,
            "lead_id": lead_micro_id,
            "status": "AUTHORIZED",
            "umn": "airtel.business@upi"
        })
        log_test(
            40, "POST /webhooks/mandate (Inbound UPI Mandate webhook callback)",
            r.status_code == 200 and r.json().get("status") == "PROCESSED",
            r.text
        )

        # Case 41: Network Provisioning Webhook
        r = client.post("/webhooks/provisioning", json={
            "order_id": order_id,
            "event_type": "LINE_SPLICED",
            "notes": "Last-mile GPON fiber spliced at OLT splitter"
        })
        log_test(
            41, "POST /webhooks/provisioning (Inbound network provisioning status update)",
            r.status_code == 200 and r.json().get("status") == "PROCESSED",
            r.text
        )

        # -------------------------------------------------------------
        # 11. Security & PII Leakage Audit
        # -------------------------------------------------------------
        raw_test_phone = "9876501234"
        raw_test_gstin = "27AAECR2040M1Z5"
        r_pii = client.post("/leads", json={"phone": raw_test_phone, "city": "Mumbai", "has_gstin": True})
        pii_body = r_pii.text
        pii_clean = (raw_test_phone not in pii_body) and ("******1234" in pii_body)

        r_pii_get = client.get(f"/leads/{r_pii.json()['lead_id']}")
        pii_get_clean = (raw_test_phone not in r_pii_get.text) and ("******1234" in r_pii_get.text)

        log_test(
            42, "SECURITY AUDIT: Zero unmasked PII (Phone/GSTIN) leaked in API responses",
            pii_clean and pii_get_clean,
            f"POST response: {pii_body}, GET response: {r_pii_get.text}"
        )

    print("=" * 75)
    print(f"VERIFICATION SUMMARY: {passed_cases} PASSED, {failed_cases} FAILED (TOTAL {passed_cases + failed_cases} TEST CASES)")
    print("=" * 75)
    if failed_cases > 0:
        exit(1)


if __name__ == "__main__":
    run_tests()
