# Project Udyam Digital: Data Privacy & Protection Policy Note
**Prepared in Compliance with the Digital Personal Data Protection (DPDP) Act, 2023**  
*Bharti Airtel Limited · Enterprise Track A · Version 1.0 (November 2026)*

---

## 1. Statutory Purpose & Commitment
Project Udyam Digital provides a digital-first acquisition, bundle configuration, and onboarding platform for Small and Medium Enterprises (SMEs) across India. In strict compliance with the **Digital Personal Data Protection (DPDP) Act, 2023**, this document outlines the technical and organizational safeguards implemented to protect Principal Data (customers, authorized signatories, and proprietors).

---

## 2. Core Privacy Engineering Principles

### 2.1 Explicit, Purpose-Bound Consent Gate
- Prior to the collection, extraction, or processing of any identification or statutory document, the Data Principal is presented with an unambiguous, notice in their chosen language (English, Hindi, Marathi, etc.).
- The system captures immutable consent records containing:
  - `consent_id` (UUIDv4)
  - Purpose Specification: `KYC_VERIFICATION`, `SERVICE_ACTIVATION`, and `STATUTORY_COMPLIANCE`.
  - Notice text version and language code.
  - Timestamp and IP audit trail.
- Document upload endpoints strictly reject any file payload if an active consent token is not present.
- Data Principals retain the right to withdraw consent at any time, which automatically halts onboarding and queues unverified data for cryptographic erasure.

### 2.2 Data Minimisation & Tiered Intake
- **No Speculative Data Gathering**: Documents are requested strictly if mandated by the products in the customer's accepted bundle.
- **Exempt Path for Non-GST Products**: For micro-enterprises choosing basic voice/connectivity products that do not legally require a GSTIN, the GST certificate upload slot is completely bypassed.
- **Registry Pre-Fill**: To eliminate excessive manual document uploads, national registries (GSTN and Udyam) pre-fill legal and trade entities upon entering the registration key, using OCR documents solely as tolerance cross-checks.

### 2.3 Strict LLM Boundary & Confidentiality
- **No PII Exposure to External AI Models**: The Conversational Advisor (powered by Groq / Llama 3.3 70B) receives only non-identifying operational parameters: business sector, employee band, branch count, city tier, and current telecom spend.
- Customer names, phone numbers, GSTINs, PANs, and raw OCR text are strictly barred from LLM system prompts, conversation histories, and tool parameters.
- KYC verification, entity matching, and rule checks are 100% deterministic and executed in local, private containers.

### 2.4 Cryptographic Protection & Masking
- **Encryption at Rest**: Sensitive identifiers, including raw GSTIN, Udyam numbers, and signatory contact details, are stored as AES-256 encrypted ciphertext via `cryptography.fernet.Fernet` with dedicated environment-managed keys.
- **Display Masking**: UI screens and logs only expose standardized masked representations:
  - Phone: `98******3210` (first 2, last 4 digits)
  - GSTIN: `27******1Z5` (first 2, last 3 characters)
  - Udyam: `UDYAM-XX-******`
- **Automated Structlog Sanitizer**: A mandatory logging filter monitors every output stream and redacts phone numbers, PAN patterns, and GSTIN sequences before disk write.

### 2.5 Private Document Storage & Presigned TTL
- Uploaded business proofs and identity documents reside in private MinIO (S3-compatible) buckets with public access disabled.
- Document inspection by authorized KYC supervisors utilizes short-lived, presigned URLs with a **10-minute Time-To-Live (TTL)**.
- Every document access, preview, and supervisor verdict generates an entry in the immutable `audit_logs` table recording actor, role, timestamp, and target resource.

### 2.6 Retention & Automated Purge Schedule
- In alignment with regulatory norms and data minimisation:
  - **Raw Document Images**: Automatically purged within **30 days** of successful service activation or journey abandonment.
  - **Extracted Metadata**: Retained for the duration of the active telecom service agreement.
  - **Consent & Audit Records**: Retained for statutory compliance periods under Department of Telecommunications (DoT) guidelines.
