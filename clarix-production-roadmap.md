# Clarix — Production-Grade Roadmap

Based on a direct audit of `mananjp/Clarix` (FastAPI + SQLAlchemy/Alembic + Postgres(Neon)/SQLite + Groq LLM + React/Vite frontend, SFDR/CSRD compliance workspace).

This is not generic advice — every item below is tied to something actually found in the code.

---

## Phase 0 — Stop-the-bleeding fixes (do before anything else, 1–3 days)

These are bugs/risks sitting in `main.py` and root scripts right now.

- [ ] **Fix duplicate route**: `PUT /api/projects/{project_id}` is defined twice (once ~line 298, again ~line 345). FastAPI silently uses the last one — delete the dead handler and diff the two to make sure you're not losing logic.
- [ ] **Lock down CORS**: `allow_origins=["*"]` combined with `allow_credentials=True` is invalid/unsafe. Replace with an explicit allow-list driven by an env var (`ALLOWED_ORIGINS`), and drop `allow_credentials` unless you truly need cookies cross-origin.
- [ ] **Fix the global exception handler**: it currently returns `HTMLResponse` with the raw exception string when `app.debug` is true. For a JSON API this should always return `JSONResponse` with a generic message in production, and the real stack trace should go to structured logs/Sentry, never the response body.
- [ ] **Stop doing schema repair in `on_startup`**: the startup event currently walks every user/project on boot to backfill `organization_id`, repair orphans, etc. This does not scale, isn't idempotent-safe under concurrent instances, and hides schema problems. Convert each of these into a one-off, reviewed data-migration script run manually/via CI, not app boot code.
- [ ] **Reconcile `fix_multi_tenant_schema.py`, `fix_multi_tenant_schema_ext.py`, `patch_db.py`** into actual Alembic revisions. Right now there's only **one** Alembic migration (`abbce384de42_enterprise_schema.py`) but multiple ad hoc patch scripts — meaning prod schema state and the migration history have already diverged. Reconstruct the true current schema, generate migrations that match it, and retire the patch scripts.
- [ ] **Add a startup config check** that fails fast if `SECRET_KEY` (used in `auth.py`) or `GROQ_API_KEY`/`DATABASE_URL` are missing/default, instead of failing later at first request with an opaque JWT error.

---

## Phase 1 — Security & access control (1–2 weeks)

Compliance software with weak authz is a liability, not just a bug.

- [ ] **Enforce RBAC server-side.** `User.role` (Reviewer / ComplianceOfficer / Administrator) exists in the model but is never checked in route handlers — every endpoint only requires `get_current_user`. Add a `require_role(*roles)` FastAPI dependency and apply it to: approve/reject answers, delete projects, user management, audit-export, settings.
- [ ] **Multi-tenant isolation audit.** The schema is org-scoped (`organization_id` on users/projects), but confirm every query filters by the current user's org — a single missed `.filter(Organization.id == ...)` is a cross-tenant data leak in a regulatory product.
- [ ] Move off `python-jose` if not already pinned to a patched release; audit `passlib[bcrypt]`/`bcrypt` versions for known CVEs — both are common supply-chain flags.
- [ ] Add refresh tokens or shorter-lived access tokens + rotation; 24-hour access tokens with no revocation list is risky for a system holding audit-grade legal data.
- [ ] Add rate limiting (e.g. `slowapi`) on `/api/auth/token`, `/api/auth/register`, and file upload endpoints.
- [ ] Validate upload size/type limits explicitly on `/api/projects/{id}/documents` and `.../documents/batch` — PyMuPDF parsing of arbitrary/huge PDFs is a DoS vector.
- [ ] Secrets: move `SECRET_KEY`, `GROQ_API_KEY`, `NEON_URL` out of ad hoc `.env` handling into a proper secrets manager (Doppler, AWS/GCP Secrets Manager, or at minimum Vault) for staging/prod; keep `.env` for local dev only. Add a `.env.example` to the repo — there currently isn't one.

---

## Phase 2 — Data layer & migration discipline (1 week, overlaps Phase 0)

- [ ] Establish **one source of truth**: all schema changes go through Alembic, no exceptions, no manual `ALTER TABLE` scripts in prod.
- [ ] Add migration CI check: a job that runs `alembic upgrade head` against a fresh throwaway Postgres container on every PR that touches `app/models.py`.
- [ ] Add DB backup/restore runbook for Neon (point-in-time recovery config, tested restore drill) — this holds regulatory disclosure history, so data loss is not an acceptable failure mode.
- [ ] Review the composite-uniqueness constraint on `FieldEvidence (project_id, regulation_field_id, document_chunk_id, extraction_method)` and the `version_no`/`is_latest` pattern on `FieldAnswer` under concurrent writes — add DB-level constraints/locking (`SELECT ... FOR UPDATE` or a partial unique index on `is_latest=True`) so two simultaneous approvals can't both end up "latest."
- [ ] Load-test the SQLite fallback path or explicitly deprecate it for anything beyond local dev — SQLite under concurrent FastAPI workers is a known bottleneck.

---

## Phase 3 — Testing & CI/CD (2 weeks)

Right now there is a single `tests_verify.py` script and no `.github/` workflows at all.

- [ ] Introduce `pytest` with a real test layout: `tests/unit/`, `tests/integration/`, `tests/e2e/`. Port the checks in `tests_verify.py` into proper pytest cases as a baseline, then expand.
- [ ] Unit tests for: `ValidationService` rules, `WhatIfEngine` scenario logic, `ExportService` markdown/HTML generation, auth token creation/verification.
- [ ] Integration tests against a real Postgres test container (not SQLite) for the ingestion → retrieval → generation → validation pipeline.
- [ ] Contract tests for the Groq-vs-fallback branch in `GenerationService` — assert both paths return schema-valid output so a Groq outage never produces malformed disclosures silently.
- [ ] Add GitHub Actions (or equivalent): lint (ruff/flake8 + eslint for frontend) → test → build → migration-check → (on tag) deploy. Currently there's no `.github` directory at all, so none of this exists yet.
- [ ] Frontend: add at least smoke tests (Vitest + React Testing Library) for the core review/approve workflow, since it's a 27-file SPA with no visible test setup.
- [ ] Add a staging environment fed by anonymized/synthetic regulatory data, not prod data.

---

## Phase 4 — Reliability of the LLM/RAG pipeline (1–2 weeks)

- [ ] Add explicit **timeouts and retry/backoff** around every Groq call in `generation.py` (currently just try/except with no timeout policy) — an API stall shouldn't hang a request indefinitely.
- [ ] Make the "local fallback" path observable: log/metric every time a response is served from the simulator vs. the real model, since compliance officers need to know when a disclosure draft is LLM-generated vs. simulated.
- [ ] Add prompt/response versioning enforcement — the schema already tracks `regulation_version`/`prompt_version`/`model_parameters`; make sure every generation path actually populates these consistently (audit this, don't assume).
- [ ] Add a circuit breaker or queue (e.g. Celery/RQ + Redis) for document ingestion + generation on large batch uploads (`/documents/batch`) so it doesn't block the request thread.
- [ ] Cost/rate monitoring on Groq usage per organization if this becomes multi-tenant SaaS — cap or throttle per-org token spend.

---

## Phase 5 — Architecture cleanup (1–2 weeks)

- [ ] Break up `app/main.py` (1,734 lines, every route in one file) into routers: `routers/auth.py`, `routers/projects.py`, `routers/documents.py`, `routers/answers.py`, `routers/what_if.py`, `routers/export.py`, `routers/audit.py`. Use `APIRouter` + `app.include_router(...)`.
- [ ] Extract the startup "maintenance & resilience engine" logic out of `main.py` entirely into `scripts/` (one-off, run manually or via CI job).
- [ ] Introduce a service-layer boundary consistently — some logic already lives in `app/services/*`, but routes still contain direct SQLAlchemy queries; push all DB access behind service/repository functions so routes stay thin and testable.
- [ ] Decouple frontend and backend deploys: currently the Vite build is compiled straight into `app/static/assets` for FastAPI to serve as one artifact. Move to independent deploys (static frontend on a CDN/Vercel/Netlify, API as its own service) so you can ship UI fixes without a backend redeploy and vice versa.

---

## Phase 6 — Observability & operations (1 week)

- [ ] Replace `print(...)` statements (used throughout `main.py` startup and services) with structured logging (`structlog` or stdlib `logging` with JSON formatter).
- [ ] Add APM/error tracking (Sentry or similar) wired into the global exception handler.
- [ ] Add health/readiness endpoints (`/healthz`, `/readyz`) that check DB connectivity and Groq reachability separately.
- [ ] Add metrics (Prometheus/OpenTelemetry): request latency, LLM call latency, fallback-usage rate, validation failure rate.
- [ ] Set up alerting on: DB connection pool exhaustion, elevated 5xx rate, Groq fallback rate spike, audit-log write failures (this last one especially — a silent audit-log failure undermines the whole compliance value prop).

---

## Phase 7 — Deployment & infrastructure (1–2 weeks)

There is currently no Dockerfile, no docker-compose, and no IaC in the repo.

- [ ] Write a `Dockerfile` for the FastAPI app (multi-stage: build frontend assets → copy into final Python image) and a `docker-compose.yml` for local dev (app + Postgres).
- [ ] Choose a target (Fly.io/Render/AWS ECS/Azure Container Apps) and write IaC (Terraform or the platform's native config) for: app service, Postgres (or confirm Neon is the permanent choice and document its scaling limits/pooling behavior under `pool_size=5, max_overflow=10`), Redis (if you add queuing in Phase 4), object storage for uploaded documents (currently local `UPLOAD_DIR` on disk — this will not survive redeploys or multi-instance scaling).
- [ ] Move uploaded documents to S3/GCS/Azure Blob instead of local filesystem storage — required the moment you run more than one app instance.
- [ ] Set up blue/green or rolling deploys with an automated Alembic migration step gated before traffic cutover.
- [ ] Define environments: dev → staging → prod, each with its own DB, secrets, and Groq key/limits.

---

## Phase 8 — Compliance-specific hardening (ongoing, but start now)

Given the product's own value proposition is regulatory audit-grade traceability, hold it to that bar internally too.

- [ ] Audit-log integrity: ensure `AuditLog` writes are transactional with the action they record (no action should be able to succeed if its audit entry fails to write) — verify this per endpoint, not assumed.
- [ ] Data retention & right-to-export/delete policy for organizations and users (relevant if this is sold into EU-regulated asset managers — GDPR applies to the platform's own user data even though the product content is about SFDR).
- [ ] Document who can see what: since roles aren't currently enforced (Phase 1), this also blocks writing an honest data-access policy for customers/auditors.
- [ ] Encryption at rest for uploaded source documents and extracted evidence, and TLS-only in transit (confirm this is enforced at the infra layer, not just assumed).
- [ ] Legal/regulatory content accuracy process: the seeded `RegulationField` data (legal basis, penalty tiers, enforcement bodies) needs a defined update/review cadence tied to actual regulatory changes — stale legal metadata in a compliance tool is a real liability, separate from software bugs.

---

## Suggested sequencing (rough timeline)

| Weeks | Focus |
|---|---|
| 1 | Phase 0 (stop-the-bleeding) + start Phase 1 (RBAC, CORS) |
| 2–3 | Finish Phase 1 (security) + Phase 2 (migrations/data layer) |
| 3–4 | Phase 3 (testing/CI) — build this in parallel with everything after, don't defer it |
| 4–5 | Phase 4 (LLM reliability) + Phase 5 (architecture cleanup) |
| 5–6 | Phase 6 (observability) + Phase 7 (deployment/infra) |
| 6+ | Phase 8 (compliance hardening) — ongoing, revisit every regulatory cycle |

A solo builder can realistically compress this to ~6–8 weeks of focused work if Phases 3 (tests) and 6 (observability) run in the background rather than as blocking gates — but do not skip Phase 0 and the RBAC piece of Phase 1 before any real users touch this, since those are active data-integrity and security holes today, not hypothetical ones.
