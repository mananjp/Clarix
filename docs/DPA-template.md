# Clarix — Data Processing Agreement (DPA) Template

**Parties**
- **Processor:** Clarix (the vendor operating the Clarix EU disclosure platform).
- **Controller:** the customer organisation (e.g. an EU asset manager or investee undertaking) purchasing/using the service.
- **Data subjects:** individuals whose personal data may be processed in course of the service (e.g. authorised users, and—where supplied by the Controller—contact/beneficial-owner data within source documents).

This template is provided as a reference for the EU asset-manager procurement review. It is **not legal advice**; both parties should have it reviewed by counsel before execution.

---

## 1. Definitions
Capitalised terms follow the meanings in Regulation (EU) 2016/679 (GDPR) unless otherwise defined. "Clarix Services" means the Clarix SFDR/ESRS disclosure application, its APIs, and associated processing.

## 2. Scope and purpose of processing
The Processor processes Personal Data only to the extent necessary to provide the Clarix Services to the Controller, including: account and access management; ingestion, parsing, storage and reporting of regulatory disclosure evidence; audit logging; and export/filing output. The Processor shall process Personal Data **only on documented instructions from the Controller**, and only for the duration and purposes described in this DPA.

## 3. Categories of data and data subjects
- **Data subjects:** Authorised end users of the Controller; and any individuals whose personal data the Controller uploads inside source documents or registers as beneficial owners.
- **Categories:** name, work email, professional role/credentials (users); and any personal data embedded in uploaded evidence documents (limited to what the Controller supplies).

## 4. Processor obligations
The Processor shall:
1. Process Personal Data only on documented instructions from the Controller, unless required to do so by EU/EEA law (in which case the Controller is notified in advance, unless that law prohibits it).
2. Ensure persons authorised to process have committed themselves to confidentiality.
3. Implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk (see **Annex A**).
4. Not engage a sub-processor without the Controller's prior general or specific authorisation; and, where a sub-processor is engaged, impose the same data-protection obligations by way of a contract.
5. Assist the Controller, taking into account the nature of the processing, in responding to requests to exercise data-subject rights under the GDPR (access, rectification, erasure, restriction, portability, objection).
6. Assist the Controller in ensuring compliance with its obligations regarding security, breach notification, data-protection impact assessments (DPIAs) and prior consultation with supervisory authorities.
7. At the Controller's choice, delete or return all Personal Data after the end of the provision of the services, and delete existing copies unless EU/EEA law requires storage.
8. Make available to the Controller all information necessary to demonstrate compliance with its obligations, and allow audits/inspections reasonably requested by the Controller.

## 5. Security (Art. 32)
The Processor shall maintain a documented security programme aligned with the controls described in **Clarix's Security Overview (`docs/security-overview.md`)**, including encryption in transit (TLS), authentication with role-based access control, encryption at rest for uploaded documents when enabled, tamper-evident integrity checks, audit logging, and EU data residency.

## 6. Confidentiality
Neither party shall disclose the other's Confidential Information (including any shared datasets) except as required by law or to those with a need to know.

## 7. Data subject rights and co-operation
The Controller may exercise data-subject rights via the Clarix data-retention and export/delete endpoints and through reasonable requests to the Processor's support function. The Processor shall respond without undue delay.

## 8. Breach notification (Art. 33/34)
The Processor shall notify the Controller without undue delay after becoming aware of a personal-data breach, providing enough information to enable the Controller to meet its notification obligations to the supervisory authority and to data subjects. The Processor shall remediate promptly.

## 9. Sub-processors
A current list is maintained and provided to the Controller on request. The Controller grants general written authorisation for the Processor to engage sub-processors who are bound by equivalent obligations; the Controller may object to new sub-processors on reasonable grounds.

## 10. Data transfers (Chapter V)
Personal Data processed under the Agreement is hosted within the EU/EEA (`DATA_RESIDENCY_REGION`). Any transfer outside the EU/EEA shall only occur under an appropriate safeguard (e.g. adequacy decision or standard contractual clauses) and documented.

## 11. Duration and termination
This DPA remains in force for as long as the Processor provides the Clarix Services. On termination, the Processor shall return or delete Personal Data per Section 4.7 within a reasonable timeframe (e.g. 30 days).

## 12. Governing law
This DPA is governed by the law governing the underlying agreement between the parties, subject to the data-protection obligations of member-state law under the GDPR.

---

## Annex A — Technical and organisational measures (summary)
| Control area | Measure | Reference |
|---|---|---|
| Access control | Role-based access control, multi-tenant org isolation, JWT auth | `app/auth.py` |
| Authentication | bcrypt hashing; enterprise SSO with verified SAML signatures | `app/services/enterprise_sso.py`, `app/services/saml_security.py` |
| Transport | TLS at infra layer | infra |
| At-rest encryption | AES-256-GCM for uploads when `ENCRYPT_AT_REST=true`; SSE on S3 | `app/services/encryption.py` |
| Integrity | SHA-256 hashes + GCM auth tag + Merkle checkpoints | `app/services/ingestion.py`, `app/services/merkle_ledger.py` |
| Incident/audit | Structured audit logs with correlation IDs; retention/export/delete | `app/services/audit.py`, `app/routers/data_retention.py` |
| Data residency | EU region config, surfaced via settings endpoint | `app/routers/settings` |