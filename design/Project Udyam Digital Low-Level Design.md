# Project Udyam Digital: Low-Level Design

YTL Hackathon 2026, Enterprise Track A · Companion to the High-Level Design · Version 1.0 · 1 November 2026

## 1. Scope and conventions

This document turns the HLD into build-level detail: stack, repository layout, schemas, algorithms, APIs and tests. It stays inside the problem statement: the four required modules (advisor, quote and checkout, Smart KYC, tracker), the stretch goals (voice or WhatsApp front end, back-office view, propensity score) and the four submission items.

| Problem statement item | Section |
| --- | --- |
| Advisor (GenAI, bundle from the catalogue, plain-language reasons, Hindi and regional languages) | 8 |
| Quote and checkout (one price, toggleable add-ons) | 7 |
| Smart KYC (upload, extraction, validation, mocked lookups, consent) | 9, 14 |
| Tracker | 10 |
| Stretch: voice or WhatsApp front end, back-office view, propensity score | 12, 13 |
| Success metrics | 15 |
| Submission: architecture diagram (HLD section 4), business case, 1-page privacy note, 3-minute demo | 14, 18 |

Mocked in the prototype: GSTIN and Udyam lookups (CSV-backed), e-sign, UPI autopay, SMS and WhatsApp delivery, and installation progress (a simulator). Out of scope: real telecom OSS or BSS integration, real payments, real DigiLocker, billing, production hardening.

Conventions: today is 2026-07-15 through a ClockPort. Money is stored as integer rupees. IDs are UUIDs. Times are stored in UTC and shown in IST. Identifiers are always masked in logs and UI.

## 2. Design inputs from the data zip

I went through every file: the README, the 25-product catalogue, the 5,000 leads, both registries and all 47 KYC images (OCR, blur and skew measurements, and cross-checks against the registries). These findings drive specific decisions below.

| Finding | Evidence | Design consequence |
| --- | --- | --- |
| Names collide in the GST registry | 2,515 of 3,534 rows share a trade name (1,861 unique). Six records are named Saffron Unisex Salon, one of them Suspended | Look up by GSTIN or Udyam number only, never by name |
| GSTIN OCR is unreliable | A quick Tesseract test on the cropped GSTIN field recovered it exactly for 5 of 11 readable certificates; the rest had O/0 confusions or dropped or doubled characters | Enter-then-verify: the owner types the GSTIN, the registry is the truth, OCR is a tolerant cross-check |
| Blur is easy to detect | Laplacian variance is 1.0 for K04's GST certificate and about 930 to 1,930 for every other image | Quality gate at 100 |
| One scan is skewed | K02's GST certificate is 1894x1446 and visibly rotated; full-page OCR garbled it | Deskew before OCR |
| Udyam dates do not reconcile | The certificate date differs from the registry date for all 9 comparable specimens (GST dates all match) | Do not validate the Udyam date; check number, name, city and state |
| Whole-string name similarity is too coarse | K07's mismatch scores 90.5 while K02's harmless OCR noise scores 94.9; comparing only the business name gives 80.0 against 94.7 | Split 'Owner (Prop. Business)' and compare the parts separately |
| Manual selling broke catalogue rules | 53 violations across 48 of 368 activated bundles (13%): P03 in tier 2 (24), P11 without a base link (9), P03 under 5 employees (7), GST-only products without a GSTIN (12), P06 under 25 employees (1) | The rules engine is a hard gate, and the business case can quote this as a cost of manual selling |
| Price sits mid-range | Activated bundle value averages 0.48 of the way between catalogue min and max; setup fees match the catalogue exactly in all 368 | Default price position 0.5; setup fees straight from the catalogue |
| Contracts are mostly 12 months | 304 of 368 are 12 months, 61 are 24, 3 are 6 | Default term is the longest minimum term among the items |
| Language mix | Hindi, English and Marathi are 76% of leads (3,810 of 5,000); ten languages in total | Full UI in three languages; the advisor replies in all ten |

## 3. Technology stack

Versions are pinned in the lock files at setup; the majors below are the target.

| Layer | Tool | Role |
| --- | --- | --- |
| Runtime | Python 3.12, Node 20 LTS | Backend, frontend build |
| API | FastAPI, Uvicorn, Pydantic v2 | Typed endpoints and schemas, SSE streaming |
| Persistence | PostgreSQL 16, SQLAlchemy 2, Alembic | Relational data, JSONB payloads, append-only events |
| Jobs | Redis with RQ | KYC extraction, tracker simulator, retention job |
| Object storage | MinIO (S3 API) via boto3 | Private document store |
| LLM | Anthropic Python SDK, Claude with tool use | Advisor and optional vision fallback; model names in env vars ADVISOR\_MODEL and VISION\_MODEL |
| OCR and vision | Tesseract with pytesseract, OpenCV (headless), Pillow | Local extraction, blur, deskew, watermark masking |
| Matching | rapidfuzz | Name and address similarity |
| Data and ML | pandas, scikit-learn, joblib | CSV loading, propensity model |
| Security | PyJWT, slowapi, cryptography (Fernet), python-magic | Auth, rate limits, field encryption, upload type checks |
| Documents | WeasyPrint | Quote and agreement PDF for the mock e-sign |
| Logging | structlog with a masking processor | JSON logs with identifiers redacted |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, react-i18next, vite-plugin-pwa | Mobile-first PWA, back-office routes in the same app |
| Voice (stretch) | Browser Web Speech API | Speech input and output in Hindi and English |
| WhatsApp (stretch) | Chat simulator plus a webhook adapter | Same advisor behind a second channel; no live WhatsApp |
| Testing | pytest, hypothesis, Playwright | Unit, property and end-to-end tests |
| Tooling | Docker Compose, Makefile, ruff | One-command run, lint |

## 4. Repository layout

```
udyam-digital/
  docker-compose.yml  Makefile  .env.example
  data/                      # the zip contents, read-only
  backend/app/
    main.py  config.py  events.py  ports.py
    catalogue/               # loader, rules.py, pricing.py, pricing_policy.yaml
    advisor/                 # state.py, tools.py, prompts/, guardrail.py, playbooks/*.yaml
    quote/                   # service.py, pdf.py
    kyc/                     # pipeline/, validators.py, registries.py, consent.py
    orders/                  # state_machine.py, simulator.py, eta.py
    leads/                   # funnel.py, queue.py, propensity/ (train.py, score.py)
    adapters/                # llm_anthropic.py, ocr_tesseract.py, storage_minio.py, notify_outbox.py
    api/                     # routers per module
    db/                      # models.py, migrations/
  backend/tests/             # unit/, property/, kyc_fixtures/, advisor_scenarios/
  web/src/                   # routes/, components/, i18n/{en,hi,mr}.json, voice/
  docs/                      # architecture.mmd, privacy-note.md, model-card.md
```

## 5. Backend structure and ports

The backend is a modular monolith. Each module exposes a service interface; modules never read each other's tables. Every state change emits an event through events.emit(), and everything outside the module that owns the data reads from events or service calls.

External dependencies sit behind ports so each can be swapped or faked in tests.

| Port | Prototype adapter | Production swap |
| --- | --- | --- |
| RegistryPort (gstin, udyam) | CSV loaded into read-only tables | Live GST and Udyam APIs |
| ExtractorPort | Tesseract and OpenCV pipeline | In-region OCR or DigiLocker fetch |
| LlmPort | Anthropic SDK | Any provider with tool calling |
| StoragePort | MinIO | Cloud object store |
| NotifierPort | Outbox table plus live feed | SMS and WhatsApp providers |
| ClockPort | Fixed date 2026-07-15, adjustable in the demo | System clock |

## 6. Data model

| Table | Key columns |
| --- | --- |
| leads | id, source, language, phone\_masked, partner\_id, status, created\_at |
| business\_profiles | lead\_id, business\_type, segment, city, tier, employees, sites, current\_internet, current\_provider, monthly\_spend, needs\[\], mobile\_lines |
| conversations, messages | lead\_id, role, content, tool\_calls (jsonb), lang, created\_at |
| quotes | id, lead\_id, version, term\_months, monthly\_recurring, one\_time, savings\_vs\_current, status |
| quote\_lines | quote\_id, product\_id, qty, unit\_price, setup, reason\_codes\[\] |
| consents | id, lead\_id, purposes\[\], notice\_version, language, accepted\_at, withdrawn\_at |
| kyc\_cases | id, lead\_id, quote\_id, consent\_id, gstin\_enc, gstin\_masked, udyam\_enc, udyam\_masked, verdict, decided\_at |
| kyc\_documents | id, case\_id, slot, storage\_key, sha256, quality (jsonb), extracted (jsonb), confidence (jsonb), delete\_after |
| kyc\_checks | case\_id, check\_code, outcome (PASS, FAIL, REVIEW, WARN), detail (jsonb) |
| orders, order\_items | order\_id, quote\_id, status, kyc\_approved\_at, eta; per item: product\_id, qty, status, eta, installed\_at |
| events | id, ts, lead\_id, order\_id, type, payload (jsonb); append-only, no update or delete grant |
| notifications | id, lead\_id, channel, template, body, sent\_at (outbox) |
| partners | id, name, cities\[\], segments\[\] |
| lead\_scores | lead\_id, score, model\_version, top\_factors (jsonb) |
| audit\_log | id, ts, actor, role, action, target, detail |

products, gstin\_registry and udyam\_registry are read-only tables seeded from the CSVs by a script. Sensitive fields (GSTIN, Udyam number, extracted ID numbers) are stored encrypted with Fernet, with a masked copy for display.

## 7. Rules engine, pricing and quote

**Inputs and outputs.** The engine is pure and stateless.

```python
@dataclass(frozen=True)
class Profile: tier: int; employees: int; sites: int; has_valid_gstin: bool; segment: str
@dataclass(frozen=True)
class Violation: product_id: str; code: str; detail: dict

def validate(profile, lines) -> list[Violation]
def repair(profile, lines) -> RepairResult   # fixed lines plus a log of what changed and why
def recommend(profile, needs, playbook) -> list[Bundle]
```

has\_valid\_gstin is true only when the registry returns the GSTIN as Active. A typed GSTIN that is Cancelled or Suspended counts as false.

**Violation codes.** TIER\_UNAVAILABLE, MIN\_EMPLOYEES, MIN\_SITES, GSTIN\_REQUIRED, DEPENDENCY\_MISSING. The catalogue column requires\_one\_of is parsed into a set of product IDs.

**Repair loop.** At most three passes, because removing a base link can orphan dependants:

1. Drop products that fail tier, size or GSTIN rules and record a removal reason.
2. For a missing dependency, add the cheapest eligible base link (by price\_min) from the allowed set, otherwise drop the dependant.
3. Re-validate until no violations remain.

target\_segments in the catalogue is used only for ranking. It is not an eligibility rule.

**Quantity defaults** (the owner can change them with steppers on the quote screen):

| Unit | Default |
| --- | --- |
| per site | number of sites |
| per user, per device (security) | employee count |
| per line | mobile\_lines slot, default 1 per employee up to 10 |
| per camera, per counter, per vehicle | asked by the advisor, defaults 4, 1 per site, and 1 |
| per number, per IP, per account, per pack | 1 |

**Pricing.** Each unit price sits inside the catalogue range at position pos. Parameters live in pricing\_policy.yaml:

```python
pos = 0.50
if term_months >= 24: pos -= 0.15
if qty >= 5:          pos -= 0.10
if segment == 'micro': pos -= 0.10
pos = min(0.90, max(0.10, pos))
unit_price = round(price_min + pos * (price_max - price_min))
```

These start values are to be calibrated, not assumed. A calibration test replays the 368 activated bundles through the pricing function and compares the result with monthly\_bundle\_value\_inr. Setup fees are summed straight from the catalogue.

**Quote structure.** Lines (product, quantity, unit price, line monthly, setup, plain-language reason), then monthly\_recurring, one\_time, first\_month\_total and term\_months. The default term is the longest minimum term among the items, and the owner can choose a longer allowed term. If the owner stated a current telecom spend and the recurring price is lower, the quote shows the saving; otherwise it shows value added and no saving claim. Each toggle calls repair() again and the response lists what changed and why.

## 8. Advisor

**State machine.** GREETING, PROFILE\_COLLECTION, RECOMMEND, QUOTE\_HANDOFF, or HANDOFF\_TO\_HUMAN. Language is set at entry from the lead record or the owner's choice.

**Slots** (Pydantic model): business\_type, city, employees, sites and has\_gstin are required. current\_internet, current\_provider, monthly\_spend, needs and mobile\_lines are optional. Slots are filled from free text through the update\_profile tool, so a single answer can fill several. The next question is the highest-priority unfilled slot, one question per turn, with a cap of 7 questions. The advisor never asks for the GSTIN in chat; the identifier is entered in the KYC step, which sits behind the consent screen.

**Segment inference.** A lookup table built from smb\_leads.csv maps the 35 business types to the four segments. For a type not in the table, the classify\_segment tool asks the LLM to choose from a fixed enum; if it is unsure, the advisor asks.

**Tools** (the only way the advisor gets facts):

| Tool | Purpose |
| --- | --- |
| update\_profile(fields) | Store extracted slot values |
| classify\_segment(business\_type) | Enum answer for unseen business types |
| get\_recommendation(profile, needs) | Returns bundles, reason codes and the quote draft from the engines |
| adjust\_bundle(add, remove) | Toggle products; returns the repaired bundle and what changed |
| explain\_rule(violation\_code, product\_id) | Plain-language cause for a blocked or removed product |
| handoff(reason) | Creates a back-office lead with a summary |

The tool loop allows at most 4 iterations per turn. Replies stream to the PWA over SSE.

**Prompt contract.** Reply in the owner's language. Keep messages to two short sentences for a phone. Ask one question per turn. State a product, price or eligibility fact only if it appears in a tool result. Explain a recommendation from the reason codes returned by the engine (for example NEEDS\_BACKUP\_LINK, FITS\_TIER, SMALL\_TEAM\_FIBRE) so the explanation is grounded, and keep product names in English with a short local-language description.

**Guardrail.** After each reply, extract every product ID (P followed by two digits) and every rupee figure, normalising Devanagari and other Indic digits. Any value not in the allowed set from the last tool results blocks the reply. The model regenerates up to twice, then a deterministic template reply is sent. Prompts carry only business-profile fields: no GSTIN, names or phone numbers.

**Playbooks** are YAML seeds that the engine then validates and repairs:

```yaml
segment: professional_offices
seed: [P02, P16, P17, P20]
add_if_need:
  mobile: [P07]
  backup: [P09]
  cctv: [P23]
  whatsapp: [P15]
prefer_term_months: 12
```

Indicative seeds for the other segments: micro retail uses P04 or P01 with P07, P19 and P15; small multi-site uses P01 or P02 per site with P09, P22, P23 and P19, adding P10 when 3 or more sites qualify; small manufacturers use P05 with P21 and P24, routed to partner or field follow-up.

**Fallback.** If the LLM times out (8 seconds) or fails twice, the same slots are shown as a short chip-based form that feeds the same engines.

## 9. Smart KYC

**Documents requested** come from the bundle. Address proof, signatory ID and the Udyam certificate are always requested (the brief and specimen set treat Udyam as required, which I have assumed). The GST certificate is requested only when the bundle has a product with requires\_gstin = Y or the owner holds a GSTIN.

**Pipeline.** Runs as an RQ job per document.

| Stage | Tool and parameters | Outcome codes |
| --- | --- | --- |
| Upload check | python-magic, PNG or JPEG, max 5 MB, short side at least 800 px | BAD\_TYPE, TOO\_LARGE, LOW\_RES |
| Quality gate | OpenCV Laplacian variance, threshold 100 | BLURRY (K04) |
| Deskew | Estimate angle from the text pixel mask; rotate if more than 1 degree | auto-corrected (K02) or UNREADABLE |
| Clean | Mask the red SYNTHETIC SPECIMEN watermark in HSV, convert to greyscale, upscale 2x for field crops | n/a |
| Classify | OCR the header band for the document title; compare with the upload slot | WRONG\_DOCUMENT |
| Extract | Tesseract page mode 6 with TSV output; parse label-anchored rows; join wrapped address lines under the place-of-business label; per-field confidence is the mean word confidence | LOW\_CONFIDENCE below 60 |
| Validate | Checks below | PASS, FAIL, REVIEW, WARN |

An optional vision-LLM fallback for low-confidence fields is controlled by EXTRACTOR=llm. It is off by default so documents stay local.

**Enter-then-verify.** The owner types the GSTIN (and Udyam number). The registry is queried by that exact key, and its record pre-fills the legal name, address and status. OCR of the uploaded certificate is then compared against the registry record, not trusted as the source. A GSTIN that fails the checksum is rejected immediately with a retype prompt.

```python
C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def gstin_ok(s):
    if len(s) != 15: return False
    t = 0
    for i, ch in enumerate(s[:14]):
        v = C.index(ch) * (1 if i % 2 == 0 else 2)
        t += v // 36 + v % 36
    return C[(36 - t % 36) % 36] == s[14]
```

This checksum validates every record in the GST registry. Structure is checked with ^\\d{2}\[A-Z\]{5}\\d{4}\[A-Z\]\[A-Z0-9\]Z\[A-Z0-9\]$, and the PAN's 4th character X is accepted.

**Validators.**

| Check | Rule | Outcome |
| --- | --- | --- |
| GSTIN status | Registry record is Active | Cancelled or Suspended: BLOCKED\_GSTIN, and the journey offers products that do not need a GSTIN (the rules engine re-runs with has\_valid\_gstin false) |
| GSTIN OCR cross-check | OCR value equals the entered value, or differs by at most 3 characters | Larger difference: FAIL; small difference: WARN |
| Name | Split 'Owner (Prop. Business)'. Business part similarity at least 90 passes, 85 to 89.9 is REVIEW, below 85 fails; owner part at least 90. Also compare the certificate's legal-name business part with its own trade name | K07 fails (80.0 against 90 or more) |
| Udyam | Format ^UDYAM-\[A-Z\]{2}-\\d{2}-\\d{7}$, present in the registry, enterprise name, city and state match; the date is not checked | Missing number: FAIL |
| Address | Normalised token match against the registry and the address proof; pincode must match exactly | Mismatch: FAIL |
| Address proof age | Bill date no older than 90 days from the ClockPort date (cutoff 2026-04-16) | Older: FAIL (K11) |
| Signatory | For a proprietorship the ID name must equal the owner part of the legal name; for an LLP or company the designation is recorded | Name mismatch: FAIL; designation Owner or Office admin on a company: WARN for the reviewer, configurable |
| ID validity | Valid-till date after today | Expired: FAIL |
| Duplicates | The GSTIN is not already attached to another active case | Duplicate: REVIEW |

**Verdict.** Any FAIL gives NEEDS\_FIX with one specific, actionable message per failure in the owner's language. No FAIL but at least one REVIEW gives MANUAL\_REVIEW and a back-office task. Otherwise PASS. WARN never blocks.

**Expected results for the 12 specimen applicants.** This is my reading from OCR and registry cross-checks. The judges' answer key is the authority, so treat these as a starting regression suite to confirm, not as ground truth.

| Applicant | Expected verdict | Reason |
| --- | --- | --- |
| K01 | NEEDS\_FIX | GSTIN is Cancelled in the registry (journey falls back to non-GST products) and the Udyam number is blank on the certificate |
| K02 | PASS | GST certificate is skewed; deskew must recover it |
| K03 | PASS | Clean control |
| K04 | NEEDS\_FIX | GST certificate is blurred, retake the photo |
| K05 | NEEDS\_FIX | Udyam certificate missing |
| K06 | PASS | Clean, but six registry records share its name, so lookup must be by GSTIN |
| K07 | NEEDS\_FIX | Legal name says Shri Physio Clinic, trade name and registry say Neelgiri Physio Clinic |
| K08, K09, K10, K12 | PASS | No problem found in the checks above |
| K11 | NEEDS\_FIX | Address proof dated 2025-10-31, 257 days old |

**Consent gate.** Every KYC endpoint rejects the request unless a valid, non-withdrawn consent record exists for the lead and purpose.

## 10. Order and tracker

**Order states.**

| State | Entered when | Next |
| --- | --- | --- |
| QUOTE\_ACCEPTED | Owner accepts the quote and sets up the mock mandate | KYC\_PENDING |
| KYC\_PENDING | Consent recorded, documents awaited | KYC\_IN\_REVIEW or KYC\_NEEDS\_FIX |
| KYC\_NEEDS\_FIX | Verdict is NEEDS\_FIX | KYC\_IN\_REVIEW after re-upload |
| KYC\_IN\_REVIEW | Documents validated; waiting on a reviewer if MANUAL\_REVIEW | KYC\_APPROVED |
| KYC\_APPROVED | Verdict PASS, or a reviewer approves | INSTALL\_SCHEDULED |
| INSTALL\_SCHEDULED | Per-item install jobs created | INSTALLED |
| INSTALLED | An item is installed | ACTIVATED once every item is installed |
| ACTIVATED | All items installed | Terminal |

Exceptions: SITE\_NOT\_FEASIBLE, INSTALL\_DELAYED, PAYMENT\_FAILED, CANCELLED. Every transition is an event, and the order's status is derived from its events.

**ETA.** Item ETA is kyc\_approved\_at plus the product's typical\_install\_days (calendar days). Order ETA is the latest item ETA. For example, Biz Fibre 300 (5 days) with cloud email, cloud backup and endpoint security (1 day each) gives 5 days after approval, against 17.6 days from lead to activation today.

**Simulator.** A worker advances items on a timer where one day is a configurable number of seconds, and an admin endpoint can jump ahead or inject a fault (fibre not feasible, payment failed, install delayed) so the demo can show each path.

**Exception handling.**

- SITE\_NOT\_FEASIBLE on P01, P02 or P03: the engine proposes P04 (5G AirFiber, available in both tiers, 2 install days). The owner sees the price difference and approves with one tap, and the ETA is recomputed.
- INSTALL\_DELAYED: when now passes the ETA the owner is notified with a new date, the order escalates to the back-office at ETA plus 3 days, and a hard flag is raised at 21 days.
- PAYMENT\_FAILED: a retry link goes out through the notifier; after 3 failures the order becomes a back-office lead.

**Tracker view.** A vertical timeline with the current step, the ETA, what the owner needs to do next in plain language, and live updates over SSE. TRACKER\_VIEWED and SUPPORT\_CONTACT events let the status-chase metric be measured.

## 11. API

All endpoints return JSON errors of the form code, message\_key, detail; the frontend localises the message\_key.

| Method and path | Purpose |
| --- | --- |
| POST /auth/otp/request, /auth/otp/verify | Phone OTP (fixed demo OTP), returns a JWT |
| POST /leads | Create a lead with source and language |
| POST /advisor/{lead}/message | Send a message; SSE stream of the reply |
| GET /leads/{id}/profile | Current profile and recommended bundle |
| POST /rules/validate | Validate a bundle for a profile (used by the UI and tests) |
| POST /quotes, PATCH /quotes/{id} | Build a quote; toggle products, quantities or term |
| POST /quotes/{id}/accept, GET /quotes/{id}/pdf | Accept; download the quote PDF |
| GET /consent/notice, POST /consents, DELETE /consents/{id} | Versioned notice, record consent, withdraw |
| POST /kyc/cases | Open a case (requires consent) |
| PUT /kyc/cases/{id}/identifiers | Enter GSTIN and Udyam number; registry lookup and pre-fill |
| POST /kyc/cases/{id}/documents | Upload a document for a slot (multipart) |
| GET /kyc/cases/{id} | Verdict, per-check results, fix messages |
| POST /esign/{quote}/request, /esign/{id}/complete | Mock e-sign, including a link for another signatory |
| POST /payments/mandate | Mock UPI autopay mandate |
| GET /orders/{id}, GET /orders/{id}/stream | Order status; SSE updates |
| POST /ops/orders/{id}/simulate | Admin: jump time or inject a fault |
| GET /ops/leads, POST /ops/leads/{id}/assign | Back-office queue and routing |
| GET /ops/kyc/review, POST /ops/kyc/{id}/decision | Manual review queue and decision |
| GET /ops/metrics/funnel | Funnel and metric views |
| POST /webhooks/whatsapp | Stretch: WhatsApp-style channel into the advisor |

## 12. Frontend

**Routes.** /start (language, OTP), /chat, /quote/:id, /consent, /kyc/:case, /sign/:quote, /track/:order, and for staff /ops/leads, /ops/review, /ops/funnel.

**Design rules.** Mobile-first, text at least 16 px, tap targets at least 44 px, quick-answer chips in the chat, amounts formatted for en-IN, numerals localised. Server state uses TanStack Query, chat and tracker streams use EventSource.

**Internationalisation.** react-i18next namespaces, with complete en, hi and mr files (76% of leads). The other seven languages fall back to English UI text while the advisor still replies in the owner's language.

**KYC screen.** Camera capture and gallery pick, an immediate preview with retake, a registry pre-fill card the owner confirms, and a status chip with the fix message for each document.

**Voice (stretch).** Web Speech API recognition with hi-IN, en-IN and mr-IN, a push-to-talk button, an editable transcript before sending, and speech synthesis for read-aloud. The button is hidden where the browser lacks support.

**WhatsApp stub (stretch).** A /wa-sim route renders the same advisor as a WhatsApp-style thread through the webhook adapter, with quotes as text and documents as image attachments.

**PWA.** Manifest and a service worker for the app shell only. KYC pages and documents are never cached.

## 13. Back-office and propensity (stretch)

**Lead queue.** Entries are created from events: ADVISOR\_UNRESOLVED (the handoff tool), ADVISOR\_ABANDONED (profile complete, no quote within 24 hours), KYC\_MANUAL\_REVIEW, SITE\_NOT\_FEASIBLE with no accepted swap, and PAYMENT\_FAILED after retries. Each entry shows the reason, a transcript summary, the profile, the quote draft and the score. Leads route to partners by city and segment, and partner attribution stays on the lead through activation. In assisted mode a partner starts the journey with the owner present, and consent is captured on the owner's own device by OTP.

**Propensity model.**

| Item | Decision |
| --- | --- |
| Data and target | smb\_leads.csv, 5,000 rows, 7.4% positive; target is outcome equal to Activated |
| Features (known at lead time) | segment, business\_type, city\_tier, state, employee\_count, num\_sites, turnover band, has\_gstin, has\_udyam, current\_internet, current\_provider, monthly\_telecom\_spend, number of products\_of\_interest, lead\_source, preferred\_language, weekday created |
| Excluded as leakage | stage dates, stage\_reached, drop\_reason, follow-up calls, bundle, value, setup, contract, churn, NPS, acquisition cost |
| Models | Logistic regression (balanced class weights) as the explainable baseline, and HistGradientBoostingClassifier; serve the logistic model unless the boosted one is clearly better on the test split |
| Validation | Train on leads created Apr to May, test on June; report ROC-AUC, PR-AUC, top-decile lift and a calibration plot |
| Output | Score 0 to 100 and the top 3 contributing factors (standardised coefficient times value) |
| Model card | docs/model-card.md, stating that the data is synthetic and the planted signals (for example GSTIN) will make it look learnable |

The score ranks leads for call priority only. It is never used to decline service.

## 14. Privacy and security implementation

| Control | Implementation |
| --- | --- |
| Consent | Versioned notice served by language; record stores purposes (kyc\_verification, service\_activation), notice version and language; KYC endpoints require a valid record; withdrawal sets withdrawn\_at and queues deletion |
| Purpose limitation | Each stored field carries a purpose tag in the schema docs; the propensity pipeline runs under a database role with no access to KYC tables |
| Data minimisation | Document list derived from the bundle; registry pre-fill instead of retyping; no identifiers asked in chat; advisor prompts carry profile fields only |
| Masking | GSTIN shows the first 2 and last 3 characters, phone the last 4; a structlog processor redacts GSTIN, Udyam, phone and ID-number patterns from every log line |
| Encryption | TLS in transit; Fernet encryption for identifiers; MinIO server-side encryption; keys from environment variables, with a re-encrypt script for rotation |
| Document access | Private bucket; presigned URLs with a 5-minute TTL; every view written to audit\_log |
| Retention | A nightly job deletes raw documents at delete\_after, default 30 days after activation or abandonment (a proposal held in config); extracted fields kept for the contract term; consent and audit records kept longer; deletions are logged |
| Access control | JWT roles: owner, partner, sales, reviewer; owners see only their own lead; reviewers see documents only for cases in review |
| Upload hardening | Magic-byte type check, size cap, image re-encoded to strip metadata, filenames replaced by UUIDs |
| LLM boundary | No identifiers to the advisor; KYC extraction runs locally; OCR text is never given to the advisor; vision fallback is off by default |
| Abuse limits | slowapi rate limits on OTP, chat and upload; at most 3 upload retries per slot |

These controls feed the one-page privacy note in docs/privacy-note.md.

## 15. Metrics and instrumentation

Events: LEAD\_CREATED, ADVISOR\_STARTED, PROFILE\_COMPLETE, RECOMMENDED, QUOTE\_ACCEPTED, CONSENT\_GIVEN, KYC\_DOC\_UPLOADED, KYC\_VERDICT, ESIGN\_DONE, MANDATE\_OK, ORDER\_CREATED, ITEM\_INSTALLED, ACTIVATED, TRACKER\_VIEWED, SUPPORT\_CONTACT, HANDOFF. Metrics are SQL views over the events table, shown at /ops/funnel next to the baseline funnel.

| Metric | Computation | Baseline | Proposed target |
| --- | --- | --- | --- |
| Lead-to-activation | ACTIVATED divided by LEAD\_CREATED | 7.4% | 12% or more |
| Time to activate | Median of ACTIVATED minus LEAD\_CREATED | 17.6 days | 7 days or less |
| Status chases per customer | SUPPORT\_CONTACT (status) per activated order | 3 | 1 or fewer |
| Acquisition cost per activation | (channel cost plus LLM and infrastructure cost per conversation plus partner fee) divided by activations, from a cost table | about ₹15,000 | ₹8,000 or less |
| 6-month churn | Production metric, not measurable in the prototype | micro 22.7% | 15% or less |

Targets are proposals for the business case.

## 16. Testing

- **Rules engine:** a parametrised positive and negative test for every catalogue rule, plus a hypothesis property test that every bundle from recommend() passes validate() and that repair() is idempotent.
- **Historical replay:** run the 368 activated bundles through validate(); expect 48 bundles and 53 violations flagged, matching section 2. The figure doubles as business-case evidence.
- **Pricing calibration:** replay the same bundles and report the median absolute error against monthly\_bundle\_value\_inr; tune pricing\_policy.yaml; setup fee sums must match exactly.
- **KYC fixtures:** the 12 applicants (47 images) with the expected verdicts from section 9, updated once the judges' key is available, plus synthetic perturbations (blur, rotate, crop) of clean images to prove detection.
- **Registry:** lookup by GSTIN, the six-record Saffron Unisex Salon collision, and Cancelled and Suspended statuses blocking.
- **Advisor scenarios:** 15 of my own, one per segment plus edge cases (tier-2 owner asks for 1G fibre, no-GSTIN owner asks for cloud telephony, 2-site business asks for SD-WAN, a Hindi conversation, a changed mind, an off-topic question, a product not in the catalogue). Each asserts that the final bundle is valid and every product and price in replies came from tool results. The judges' 15 scenarios run through the same harness.
- **Guardrail:** a mocked LLM that emits a fake price and a fake product ID must be blocked and replaced by the fallback.
- **Privacy:** captured logs contain no unmasked GSTIN, Udyam or phone number; KYC without consent returns 403; withdrawal triggers deletion.
- **End to end:** Playwright runs the demo path from Hindi chat through quote, consent, KYC (K04 retake then pass), e-sign and tracker.

## 17. Build order

| Step | Deliverable | Done when |
| --- | --- | --- |
| 1. Foundation | Compose stack, DB models, CSV seed, events | The stack starts with one command and registries are queryable by key |
| 2. Rules and pricing | rules.py, pricing.py, tests | Property tests pass and the historical replay flags 48 bundles |
| 3. Advisor core | Slots, tools, guardrail, playbooks, SSE chat | The 15 own scenarios pass with the real LLM and with the fallback |
| 4. Quote and checkout | Quote service, toggles, PDF, mock e-sign and mandate | A toggle changes the price and shows what changed |
| 5. Consent and KYC | Consent, pipeline, validators, review states | K01 to K12 match section 9 |
| 6. Order and tracker | State machine, ETA, simulator, SSE | Each injected fault produces the right state and message |
| 7. Hardening | Masking, retention job, rate limits, hi and mr UI, fallback form | Privacy tests pass |
| 8. Stretch | Back-office, propensity, voice, WhatsApp simulator | Done in that order of value |
| 9. Submission | Architecture diagram, 10-slide business case, privacy note, demo video | Video is under 3 minutes |

## 18. Demo script (3 minutes)

- 0:00 to 0:20: the problem in numbers (7.4% conversion, 17.6 days, 3 chases).
- 0:20 to 1:00: a dental clinic owner in a tier-2 city talks to the advisor in Hindi. The bundle is recommended with reasons. The owner asks for 1G fibre; the engine explains it is not offered there and proposes Biz Fibre 300.
- 1:00 to 1:25: one price, toggle cloud backup, remove the base link and see the dependency repair message, and the saving against current spend.
- 1:25 to 2:15: consent screen, then GSTIN entry with registry pre-fill. Upload K04 (blur message), K11 (stale bill message) and K01 (cancelled GSTIN, fall back to non-GST products), then a clean applicant passes.
- 2:15 to 2:35: e-sign and mandate, and the order appears with a 5-day ETA.
- 2:35 to 2:50: tracker view; inject fibre not feasible and approve the AirFiber swap with one tap.
- 2:50 to 3:00: back-office queue with scores and the funnel view.

## 19. Assumptions and open points

- Udyam is required for every applicant and the GST certificate only when needed. Confirm with the organisers.
- Quantity defaults and pricing-policy parameters are starting values to calibrate.
- The K01 to K12 verdict table is my reading. The judges' key decides, and the signatory-designation rule is deliberately soft.
- Deskew, watermark masking and OCR thresholds were measured on a quick pass with Tesseract 4.13 and need tuning on the full set.
- Retention periods are proposals.
- The submission deadline and team size are still unknown, which is why stretch work comes last in section 17.
