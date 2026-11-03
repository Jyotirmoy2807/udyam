# Project Udyam Digital: High-Level Design

YTL Hackathon 2026, Enterprise Track A · Prepared for Jyotirmoy · Version 1.0 · 1 November 2026

## 1. Purpose and scope

This document describes the high-level design of a digital-first acquisition and onboarding journey for Accel Business. A small business owner discovers the right bundle, buys it, completes KYC and tracks activation on a phone, in their preferred language, with minimal human effort.

It covers architecture, components, key flows, data, rules, privacy and security, and a build plan. It does not cover detailed API schemas, UI wireframes or real telecom back-end integration. All data is synthetic, and the mock registries stand in for real GSTIN and Udyam services.

## 2. What the design must fix

Of 5,000 leads in Apr–Jun 2026, only 368 (7.4%) activated. The drop reasons in smb\_leads.csv map directly to design features, which is the reasoning behind every major choice below.

| Drop reason (leads lost) | Design response |
| --- | --- |
| Unreachable, wrong number, not interested (1,594 at Lead stage) | Self-serve entry with phone OTP at the start; no sales call needed to begin |
| No time for a visit, visit not scheduled (827 at Contacted) | The advisor replaces the discovery visit; a 5-minute chat |
| Price too high, competitor cheaper (621 at Needs assessed) | One transparent price, right-sized bundle, savings shown against the owner's current telecom spend |
| Quote too complex, quote too slow (385) | Instant quote in plain language, with product codes hidden |
| Missing document, paperwork too long, details mismatch, signatory unavailable (273 at Quote accepted) | Tiered KYC (only what the bundle needs), registry pre-fill, pre-validation before submit, e-sign link sent to the signatory |
| Install delay over 21 days, site not feasible for fibre, payment failed, cancelled (220 after KYC) | Tracker with proactive alerts, automatic 5G AirFiber fallback for infeasible sites, UPI autopay at checkout |

Two more findings shape the design. Activation is 9.6% with a GSTIN against 2.0% without, and many products require one, so the journey needs a lighter path for owners without a GSTIN. Customers who chased status 4 or more times churned at 23% against 6–14% for fewer chases, so the tracker is a retention feature as well as a support-cost feature.

## 3. Design principles

1. The LLM proposes, deterministic engines decide. Eligibility, price and KYC verdicts come from rules and validators. The LLM converses, extracts and explains, and it never invents a product, a price or a verdict.
2. A modular monolith with ports and adapters. Each bounded context sits behind an interface, and the registries, OCR, LLM and notifications are swappable adapters. This is the right size for a hackathon and has a clean path to separate services.
3. Privacy by design. Collect the minimum, gate KYC behind consent, mask identifiers, and bind each piece of data to a stated purpose.
4. One event log is the source of truth for the journey. The tracker, the funnel metrics and the back-office view are all derived from the same immutable events.
5. Fail to a human, never to a dead end. Any low-confidence or blocked path becomes a back-office lead with context attached.

## 4. Architecture overview

```
 Owner: phone PWA (Hindi / English / regional)      Partner / sales: back-office web
        |        optional: WhatsApp / voice stub               |
        +---------------------- HTTPS -------------------------+
                                 |
        API layer (FastAPI): OTP auth, i18n, rate limit, request IDs, PII-masked logs
                                 |
  +-----------+-----------+-----------+-----------+-----------+-----------+
  | Advisor   | Catalogue | Quote &   | KYC       | Order &   | Lead &    |
  | (LLM      | & rules   | pricing   | (consent, | tracker   | insights  |
  | orchestr.)| engine    |           | extract,  | (state    | (funnel,  |
  |           |           |           | validate) | machine)  | propensity)|
  +-----------+-----------+-----------+-----------+-----------+-----------+
                                 |
  Event log + Postgres | Object store (docs) | Job queue | Registry adapters | LLM adapter
                       |                     |           | (GSTIN, Udyam)    | OCR adapter
```

Requests flow top to bottom. Every context writes events to the shared log. Contexts call each other only through their public interfaces, never through each other's tables.

## 5. Components

**Experience layer.** A mobile-first PWA built around a chat-led flow: advisor, quote, consent, document upload, e-sign, tracker. UI strings are externalised for i18n and the owner's preferred language is stored on the lead. The same API serves a WhatsApp or voice front end as a stretch goal, because the advisor is channel-agnostic. The back-office view is a separate web app on the same API.

**Advisor service.** Orchestrates the conversation with an LLM using tool calls. It holds the conversation state, extracts structured profile fields from free text, asks the next best question, and turns engine output into a plain-language recommendation. Details are in section 8.

**Catalogue and rules engine.** Loads product\_catalogue.csv into typed rules and answers one question: given this business profile and this set of products, what is valid? It is pure, stateless and unit-testable against the judge scenarios. It enforces:

- city-tier availability, minimum employees and minimum sites
- requires\_gstin (a valid, active GSTIN)
- requires\_one\_of dependencies, for example failover (P09) needs a base link, and managed SD-WAN (P10) needs 3 or more sites plus a base link

When a bundle is invalid it returns the failing rule as a machine-readable reason, which is what the advisor explains to the owner.

**Quote and pricing service.** Builds one transparent quote from a validated bundle. It shows recurring monthly price, one-time setup fees and contract term as separate lines, plus a first-month total. Add-ons can be toggled, and each toggle re-runs the rules engine, so removing a base link also removes or flags dependants. Price is chosen inside each product's min-max range by a documented rule: longer contract and more units move toward the lower end. It also shows savings against the owner's stated current spend where that is true.

**KYC service.** Handles consent capture, document intake, extraction, validation against the mock registries, and a verdict. Details are in section 7.

**Order and tracker service.** An order state machine driven by events. Each product has a typical\_install\_days value. The bundle's expected activation date is the latest of its items measured from KYC approval, and the tracker shows that date and the current step. Section 6 lists the states.

**Lead and insights service.** Records the funnel, computes the success metrics, and powers the back-office lead queue and propensity score (section 11).

**Notification adapter.** Sends status updates and the e-sign link by SMS or WhatsApp. Mocked in the prototype and logged to a visible outbox so it can be shown in the demo.

## 6. Key flows

**Journey.**

1. Entry. Owner opens the link, WhatsApp or website, picks a language and verifies the phone by OTP. A lead is created with its source recorded.
2. Discovery. The advisor asks about business type, size, sites, city, current internet and spend, and needs. It stops as soon as the rules engine has enough to recommend.
3. Recommendation. The engine produces candidate bundles and the advisor presents one primary choice with a reason for each product, and one cheaper alternative.
4. Quote. The owner sees one monthly price, setup fees and term, and toggles add-ons.
5. Consent. A clear notice states what is collected, why, for how long, and who sees it. Nothing is uploaded before consent is recorded.
6. KYC. Owner enters or confirms GSTIN and Udyam number. Registry data pre-fills the form. Documents are uploaded, extracted and validated, with specific fixes shown immediately.
7. e-Sign and payment. e-Sign is mocked, with a link that can go to a different signatory. Payment is mocked as a UPI autopay mandate.
8. Order. Per-product install jobs are created with expected dates.
9. Tracker. The owner checks status on one screen with no call needed, and receives proactive alerts on delay.

**Order states.** Quote accepted, KYC pending, KYC in review, KYC approved, installation scheduled, installed, activated. Exceptions are site not feasible (automatic AirFiber fallback offered), installation delayed past 21 days (alert to owner and back-office), and payment failed (retry link).

**Handoff flow.** If the advisor cannot place the owner (an edge case, a request outside the catalogue, or repeated misunderstanding), or KYC lands in manual review, a lead is created in the back-office queue with the transcript summary, profile and failure reason.

## 7. KYC design

**Tiered collection.** The document list is derived from the bundle. If no product in the bundle requires a GSTIN, the GST certificate is not requested. This is data minimisation and it also removes friction for micro businesses. Whether a lighter KYC path is acceptable for non-GST products is an assumption to state explicitly in the privacy note.

**Pipeline.** Each document runs through the same stages:

1. Quality gate: reject blurred, cropped or low-resolution images before extraction, with a plain retake message.
2. Classification: confirm the document type matches the slot it was uploaded to.
3. Extraction: pull fields into a fixed schema with a confidence per field, through an Extractor interface.
4. Validation: run deterministic checks (below).
5. Verdict: Pass, Needs fix (specific, actionable message), or Manual review (routed to back-office).

**Validation matrix.**

| Check | Rule |
| --- | --- |
| GSTIN format | 15 characters with valid checksum; the 4th PAN character X is accepted |
| GSTIN registry | Must exist and be Active; Cancelled and Suspended are blocked |
| Udyam number | Valid format and present in the Udyam registry |
| Name match | Certificate name vs registry legal or trade name, fuzzy with a threshold |
| Address match | GST address vs address proof, fuzzy, pincode checked |
| Cross-document | Business name and state consistent across GST, Udyam and address proof |
| Address proof age | No older than 90 days against a configurable today, set to 2026-07-15 |
| Signatory | ID name consistent with the authorised person; for proprietorships the proprietor name appears in the legal name |
| ID validity | Not expired, and the ID type is accepted |
| Duplicates | The same GSTIN is not already under a different applicant |

The 47 specimen images for K01–K12 are the regression suite. Each planted problem must produce the right verdict, and the matrix above should be extended as each applicant is reviewed.

**Extractor interface.** The prototype can use a vision-capable LLM or a local OCR engine behind the same interface. In production the preferred route is DigiLocker or a registry fetch, which avoids uploading images at all, and an in-region OCR service for scans. Registry adapters read the CSV files in the prototype and are replaceable with live APIs.

## 8. Advisor design

**State.** The advisor keeps a profile with slots: business type, segment, employees, sites, city and tier, current internet and provider, monthly spend, needs, and whether a GSTIN exists. It asks only for missing slots that change the recommendation, which keeps the conversation short.

**Tools.** The LLM can call update\_profile, get\_recommendation, get\_quote and explain\_rule. All products, prices and eligibility come from tool results. The LLM never produces them from its own knowledge.

**Guardrails.** A post-check scans each reply, and any product ID or rupee amount not present in the tool results blocks the reply, which is regenerated. Prompts contain business-profile fields only: no GSTIN, no names, no phone numbers.

**Language.** The owner's language is set at entry and the advisor replies in it. Product names stay in English with a one-line local-language description.

**Segment playbooks.** Indicative starting bundles, always validated by the rules engine:

| Segment | Starting bundle | Notes |
| --- | --- | --- |
| Micro retail and services | 5G AirFiber or Biz Fibre 100, business postpaid line, Cloud POS, WhatsApp starter | Keep near the roughly ₹2,500 a month this segment spends |
| Professional offices | Biz Fibre 300, cloud email, cloud backup, endpoint security, postpaid lines | Uptime and data security are the pitch |
| Small multi-site | Fibre per site, failover, secure Wi-Fi, CCTV, POS; SD-WAN when 3 or more sites qualify | One bill and central management |
| Small manufacturers | Leased line, managed firewall, machine monitoring | Higher-touch; route to partner or field force |

**Fallbacks.** If the LLM is unavailable, the advisor degrades to a short form-based questionnaire that feeds the same engines, so the demo never depends on one service.

## 9. Data model

Core entities, each with timestamps and a lead ID for traceability:

- Lead, Business profile
- Conversation, Message
- Quote, Quote line
- Consent record (purpose, text version, timestamp, language)
- KYC case, KYC document, Extracted field, Validation result
- Order, Order item, Order event (immutable)
- Partner attribution
- Audit log

The event log is append-only. The tracker, funnel metrics and lead queue are projections of it. Order status is the replay of its events, so an auditor can see how every state was reached.

## 10. Privacy and security

| Concern | Design choice |
| --- | --- |
| Consent | Versioned notice shown and recorded before any KYC upload; withdrawal supported |
| Purpose limitation | Each field is tagged with its purpose; KYC data is not used for marketing or model training |
| Data minimisation | Documents requested only if the bundle needs them; registry pre-fill replaces re-typing |
| Masking | GSTIN, Udyam and phone are masked in logs and UI, for example the first 2 and last 3 characters of a GSTIN |
| LLM exposure | No identifiers in advisor prompts; production KYC extraction runs through an in-region adapter or DigiLocker |
| Storage | Encryption at rest and in transit; documents in private object storage with short-lived signed URLs |
| Access | Role-based: owner, partner, sales, reviewer; reviewer access to documents is logged |
| Retention | Proposed: raw documents deleted within 30 days of activation, or of abandonment; extracted fields kept for the contract period; consent and audit records kept longer |
| Audit | Every document view, verdict and override is recorded |

These choices feed the one-page privacy note. Retention periods are proposals and should be labelled as such.

## 11. Back-office and propensity (stretch)

**Lead queue.** Shows leads the advisor could not close with the reason: abandoned at a given step, KYC manual review, ineligible request, or payment failure. Leads route to the field force or channel partners by city and segment, and partner attribution is preserved so the digital journey adds to their work. A partner can also run the journey with the owner (assisted mode), with the owner's own consent captured on the owner's device.

**Propensity score.** A gradient-boosted or logistic model trained on smb\_leads.csv, predicting activation. Features: segment, city tier, has\_gstin, has\_udyam, current internet, lead source, employees, sites, monthly spend and products of interest. Fields that only exist after the outcome (stage dates, follow-up calls, bundle bought, NPS) are excluded to avoid leakage. Evaluate with a time split (train Apr–May, test June) and report lift in the top decile. The score ranks leads for call priority and is shown with its top contributing factors.

## 12. Success metrics and instrumentation

Each metric is computed from the event log.

| Metric | Baseline | Proposed target |
| --- | --- | --- |
| Lead-to-activation conversion | 7.4% | 12% or more |
| Time to activate | 17.6 days | 7 days or less |
| Status-chase calls per customer | 3 | 1 or fewer |
| Acquisition cost per activated customer | about ₹15,000 | ₹8,000 or less |
| 6-month churn | micro 22.7% | 15% or less |

Targets are proposals for the business case. Churn cannot be measured inside the prototype, so it is stated as a production metric with the baseline from the data.

## 13. Technology choices

| Layer | Choice | Reason |
| --- | --- | --- |
| Frontend | React PWA with an i18n library | Mobile-first, installable, easy language switching |
| Backend | Python with FastAPI | Single language for API, OCR and ML; typed and fast to build |
| Database | PostgreSQL | Relational plus JSON, append-only event table |
| Queue | Redis-backed worker, or Postgres jobs | Asynchronous KYC extraction without blocking the request |
| Object store | S3-compatible (MinIO locally) | Private documents with signed URLs |
| LLM | Claude via API with tool use; model set by configuration | Strong multilingual support and structured tool calls |
| Extraction | Vision LLM or local OCR behind the Extractor interface | Swappable; production route avoids uploads |
| ML | scikit-learn | Propensity model, reproducible in a notebook |
| Deployment | Docker Compose on one VM | Simple demo; services stay separable |

## 14. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| LLM invents a product or price | Tool-sourced facts only, plus the post-check guardrail |
| OCR errors on poor images | Quality gate, per-field confidence, manual-review path |
| LLM outage during the demo | Form-based fallback feeding the same engines |
| Rules diverge from the catalogue | Rules generated from the CSV with unit tests for every constraint |
| Privacy shortcuts under time pressure | Consent gate and masking built in the first milestone, not added later |
| Scope creep into stretch goals | Core journey completed and demoed end to end before any stretch work |

## 15. Build plan

1. Foundation: data loading, catalogue rules engine, registry adapters, event log, and unit tests against the catalogue constraints.
2. Journey core: advisor, quote and toggles, consent screen.
3. KYC: extraction, validation matrix, verdicts, run against all 47 specimen images.
4. Order and tracker: state machine, expected dates, exception handling.
5. Hardening: guardrails, language coverage, fallback path, masked logging.
6. Stretch, if time remains: back-office queue, propensity score, WhatsApp or voice front end.
7. Submission: architecture diagram, business case, privacy note, and a 3-minute demo script that walks the journey and a KYC failure.

## 16. Assumptions and open questions

- A lighter KYC path for products that do not require a GSTIN is a design assumption and should be stated as one.
- Bundle term rules (one term for the whole bundle versus per product) need confirming against the catalogue's min\_contract\_months.
- The submission deadline and team size are unknown and decide how much of section 11 is realistic.
- The submission template looks incomplete, so confirm the required format with the organisers.
