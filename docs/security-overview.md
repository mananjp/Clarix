# Clarix — Security Overview (one-page)
**Version:** 1.0 · **Applies to:** Clarix SFDR/ESRS disclosure platform

## 1. Identity & Access
- **Authentication:** JWT (signed with a 64-hex `SECRET_KEY`) + bcrypt password hashing. Passwords are never stored in plaintext.
- **Authorization:** role-based access control (`UserRole`, `require_role`); multi-tenant organization isolation enforced on queries.
- **Single Sign-On (SSO):** enterprise SAML 2.0. Assertions are **cryptographically verified** (XML digital signature — RSA-SHA256/SHA1, exclusive C14N, per-Reference digest check, Issuer pinning, `NotBefore/NotOnOrAfter` window). **SSO is refused at startup if no IdP certificate/issuer is configured** (`assert_sso_secure`), so unsigned assertions cannot be accepted.
- **Rate limiting:** SlowAPI per-route limits (`app/limiter.py`).

## 2. Data Protection
- **In transit:** TLS enforced at the infrastructure layer (load balancer / ingress).
- **At rest (documents):** uploaded source files are encrypted with **AES-256-GCM** (`app/services/encryption.py`) when `ENCRYPT_AT_REST=true`. Files on disk are always ciphertext; the key is provided via `ENCRYPTION_KEY` (base64, 32 bytes) or persisted to `data/encryption.key`. With the S3 backend, server-side encryption (SSE-S3/SSE-KMS) is applied by bucket policy.
- **At rest (database):** the managed Postgres is encrypted at rest by the hosting provider. Neon stores inactive data on [NVMe instance volumes encrypted with an **AES-256** hardware block cipher](https://neon.com/docs/security/security-overview) and manages customer/sensitive data encryption keys via **AWS KMS** (with key-rotation) on AWS. So no application-level encryption is applied and SQL queryability/integrity (e.g. exact token lookup for supplier intake, unique indexes) is preserved. Application-layer `pgcrypto` on specific columns is deliberately not used here because it would break the intake token index/lookup and is unnecessary given host-level encryption; see gap 8.
- **Integrity & tamper-evidence:** SHA-256 `file_hash` per document + **AES-GCM authentication tag** (tamper detection) + immutable Merkle audit checkpoints (`app/services/merkle_ledger.py`).
- **Audit logging:** structured logs with request correlation IDs (`app/logging_config.py`, `app/services/audit.py`) for access and changes.
- **Retention & portability:** GDPR data-retention and right-to-export/delete endpoints (`app/routers/data_retention.py`).
- **EU data residency:** region/vendor configurable (`GET /api/settings/data-residency`), default `eu-central-1` / AWS.

## 3. Application security
- Secrets kept out of source: `.env` + `${VAR:?}` required-vars in `docker-compose`; `.env.example` documents every var.
- Dependency hygiene checked in CI (lint via ruff in `app/`+`tests/`; tests run on every push).
- Inputs from external parties (supplier intake via token) are validated and rate-limited.

## 4. Key controls vs. SOC 2 TSC
See `docs/SOC2-readiness.md` for the full control-evidence mapping. This doc is the at-a-glance security summary for EU asset-manager procurement review.

## 5. Startup safeguards
- `assert_sso_secure` fails fast if SSO is configured without an IdP certificate.
- `main.py` refuses to start if `SECRET_KEY` is missing.