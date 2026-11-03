# Project Udyam Digital: 3-Minute Demo Video & Walkthrough Script
**YTL Hackathon 2026 · Enterprise Track A (Airtel Business)**  
*Target Timing: Exactly 3 Minutes (180 Seconds)*

---

## Demo Schedule & Voiceover Breakdown

### Act 1: The Problem & The Baseline (0:00 – 0:25)
- **Visual**: Start on `/` (Home Page) showing the Executive Benchmark Card.
- **Narrator**:
  > *"Welcome to Project Udyam Digital for Airtel Business. In Q1 2026, out of 5,000 SMB leads, only 368 activated — a dismal 7.4% conversion rate. The root causes were offline sales visits, 18-day activation waits, complex quotes, and tedious paperwork that caused 3 chase calls per customer and a 23% churn rate. Today, we show you how Udyam Digital transforms this into a 5-minute digital-first onboarding experience."*
- **Action**: Tap **"Start Instant Journey"** or navigate to `/start`.

---

### Act 2: Multilingual AI Advisor & Right-Sizing (0:25 – 1:00)
- **Visual**: `/start` -> `/chat` (Language selected: Hindi `hi`).
- **Narrator**:
  > *"Our customer, Rajesh, runs a dental clinic with 8 staff across 2 branches in Pune (a Tier-2 city). Instead of waiting days for an account executive, Rajesh chats with our AI Enterprise Advisor in Hindi. The advisor extracts his profile and queries our deterministic catalogue engine."*
- **Action**:
  - Type or tap quick prompt: *"मुझे क्लिनिक के लिए 1Gbps फाइबर चाहिए"* (I want 1Gbps fiber for my clinic).
  - The Advisor responds immediately in Hindi, explaining via the catalogue rules that 1Gbps (`P03`) is restricted to Tier-1 metros, and instead recommends **Biz Fibre 300 (`P02`)** along with Cloud Backup (`P15`) and Static IPv4.
- **Narrator**:
  > *"Notice how the LLM never hallucinates. Rule checks and pricing are 100% deterministic, eliminating the 13% catalogue violations previously made by manual sales reps."*
- **Action**: Tap **"Generate Official Quote"** (`/quote/...`).

---

### Act 3: Transparent Quote & Repair Loop (1:00 – 1:25)
- **Visual**: `/quote/:id` screen.
- **Narrator**:
  > *"Rajesh receives an instant, transparent quote showing monthly commitments, setup fees, and clear contract terms. He can toggle add-ons in real time. If he removes the base fiber link, our catalogue repair loop instantly notifies him that dependent cloud security services require a base link. Most importantly, it shows him saving ₹1,200 against his previous telecom spend."*
- **Action**:
  - Show add-on toggling.
  - Tap **"Accept Quote & Proceed to KYC"**.

---

### Act 4: DPDP Consent & Smart KYC Automation (1:25 – 2:05)
- **Visual**: `/consent` -> `/kyc/:caseId`.
- **Narrator**:
  > *"Under the DPDP Act 2023, data minimisation and consent are mandatory. Nothing is ingested without explicit consent. When Rajesh enters his GSTIN, our system pre-fills entity details directly from the national GSTN registry."*
- **Action**:
  - Show specimen auto-loader.
  - Select **K04 (Blurry specimen)** -> Instant rejection: *"Image quality below 100 Laplacian threshold. Please retake a clear photo without motion blur."*
  - Select **K11 (Stale bill)** -> Instant rejection: *"Electricity bill is older than 90 days."*
  - Select **K02 or K03 (Clean specimen)** -> Computer vision runs deskewing, fuzzy RapidFuzz registry cross-checks, and yields an automated **PASS** verdict in seconds!

---

### Act 5: e-Sign, Mandate & Live Tracker with Self-Healing (2:05 – 2:40)
- **Visual**: `/sign/:quoteId` -> `/track/:orderId`.
- **Narrator**:
  > *"Rajesh completes Aadhaar e-Sign with a single tap, authorizes his NPCI UPI Autopay mandate, and his enterprise order is created with a 2-day SLA."*
- **Action**:
  - Sign and authorize mandate -> lands on Live Order Tracker (`/track/...`).
  - Demonstrate Exception Handling: In the Tracker Control Deck, trigger **"Simulate Site Not Feasible (Fiber unavailable)"**.
  - The UI updates over Server-Sent Events (SSE). Instead of cancelling, the system offers an automated **5G AirFiber swap (`P04`)**.
  - Rajesh taps **"Accept 5G AirFiber Swap"** — order items update instantly and activation ETA recalibrates without a single phone call!

---

### Act 6: Back-Office Operations, ML Propensity & WhatsApp (2:40 – 3:00)
- **Visual**: Quick tour of `/ops/leads`, `/ops/review`, and `/wa-sim`.
- **Narrator**:
  > *"For operations teams, our Back-Office Lead Queue ranks every dropped or escalated lead using an explainable ML Propensity score and automatically routes them to the nearest channel partner. Supervisors have a dedicated KYC desk with presigned MinIO previews. And for owners on the go, our WhatsApp Business simulator executes the exact same catalogue rules, quotes, and document verifications."*
- **Visual**: Return to `/ops/funnel`.
- **Narrator**:
  > *"The result? Conversion doubles from 7.4% to 14.2%, activation time plummets from 17.6 days to 2 days, and status chases drop to zero. That is Project Udyam Digital. Thank you!"*

---

## Quick Demo Checklist for Judges
1. **Frontend PWA**: `http://localhost:5173`
2. **Backend API Docs**: `http://localhost:8000/docs`
3. **Core Routes**:
   - `/start` - Phone OTP authentication (Any 10-digit number, Demo OTP: `123456`)
   - `/chat` - AI Advisor in English, Hindi, or Marathi
   - `/quote/:id` - Interactive bundle pricing & PDF download
   - `/consent` - DPDP statutory notice
   - `/kyc/:id` - Smart KYC with specimen test fixtures
   - `/sign/:id` - Aadhaar e-sign & UPI mandate
   - `/track/:id` - Live order tracker & AirFiber fallback simulator
   - `/ops/leads` - Back-office ML lead queue
   - `/ops/review` - Supervisor document inspection & manual decision
   - `/ops/funnel` - Funnel analytics & append-only audit stream
   - `/wa-sim` - WhatsApp Business simulator
