# Clarix — SOC 2 Type II Readiness

This document formalizes Clarix's SOC 2 Type II readiness position. It maps the
five SOC 2 Trust Services Criteria (TSC) categories to the control evidence
already present in the codebase and documents the remaining gaps.

## Control-mapped evidence already in the codebase

| SOC 2 TSC | Built-in control | Code reference |
|---|---|---|
| Security | Role-based access control (`UserRole`, `require_role` dependency) | `app/models.py`, `app/auth.py` |
| Security | Authentication via JWT + bcrypt hashing | `app/auth.py` |
| Security | Multi-tenant org isolation on queries | routers, `organization_id` filters |
| Security | Rate limiting (SlowAPI) | `app/limiter.py`, `app/routers/*` |
| Security | Transport security (TLS enforced at infra layer) | infra |
| Confidentiality / Availability | Audit logging with request correlation IDs | `app/logging_config.py`, `app/services/audit.py` |
| Confidentiality | Data retention & right-to-export/delete endpoints (GDPR) | `app/routers/data_retention.py`, `app/services/audit.py` |
| Integrity | Document SHA-256 hash integrity verification | `app/services/ingestion.py` |
| Integrity | Immutable Merkle audit checkpoints / cryptographic proofs | `app/services/merkle_ledger.py` |
| Integrity | Versioned, evidence-linked field answers (`is_latest`) | `app/models.py` |

## Remaining gaps to close before a SOC 2 Type II assessment

1. **Formal control documentation** — map each TSC to a documented policy,
   procedure, and evidence artifact. This readiness doc is the starting point,
   not the deliverable.
2. **Access reviews** — schedule recurring review of user access/roles.
3. **Incident response runbook** — define and test incident response.
4. **Change management** — enforce the CI/CD pipeline (lint → test → build →
   security scan) and require peer review before production merges.
5. **Vendor risk management** — document the LLM (Groq) and any infra vendors.
6. **Backup & disaster recovery** — documented restore drill for the DB
   (regulatory disclosure history must be recoverable).
7. **Security awareness training** — evidence of team training.
8. **Encryption at rest** — confirm/config for uploaded documents and DB.

## EU data residency

Under **Section 2.3**, data residency is now env-configured and surfaced at
`GET /api/settings/data-residency`:

- `DATA_RESIDENCY_REGION` (default `eu-central-1`)
- `DATA_RESIDENCY_VENDOR` (default `aws`)
- `DATA_RESIDENCY_STATEMENT`

EU asset managers should set these to their hosting region prior to piloting.
