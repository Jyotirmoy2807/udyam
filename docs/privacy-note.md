# Project Udyam Digital - Data Privacy & Protection Policy

## 1. Statutory Compliance
This system adheres to the Digital Personal Data Protection Act (DPDP), 2023.

## 2. PII Protection Architecture
- Sensitive identifiers (GSTIN, Udyam, ID numbers) are encrypted at rest using `cryptography.fernet.Fernet`.
- Masked versions (`gstin_masked`, `phone_masked`) are stored and presented in UI/logs.
- Structlog filter redacts GSTIN (15 chars), Udyam (`UDYAM-XX-00-XXXXXXX`), and phone numbers from logs.
- KYC documents are purged according to a strict 30-day retention schedule.
