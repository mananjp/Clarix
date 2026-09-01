# Clarix — Market & Competitor Analysis + Product Gaps for Corporate-Grade Use

Scope: EU sustainability/ESG regulatory disclosure software — the market Clarix's current schema (`RegulationField`, PAI indicators, legal-basis/penalty metadata, `FieldAnswer`/`FieldEvidence`) is clearly built for: **SFDR Principal Adverse Impact (PAI) reporting**, with room to extend into CSRD.

---

## 1. The market landscape

This space has three distinct tiers of vendor, and Clarix currently sits at the bottom rung of the third one.

### Tier 1 — Full ESG data platforms (the category leaders)
**Novisto, Workiva, Position Green, Sphera, IBM Envizi, Enablon, Sweep, Greenomy (now part of Position Green Group as of Sept 2025).**

Their common architecture: a **multi-framework metric library** — a data point is entered once and automatically populates CSRD/ESRS, GRI, SASB, TCFD, ISSB S1/S2, CDP, EU Taxonomy, *and* SFDR simultaneously, because most of these frameworks share underlying data points. This is the single biggest structural differentiator in the market — vendors compete on how many frameworks one dataset can serve, not on how well they handle one framework.

On top of that, the leaders layer:
- **Double materiality assessment modules** (a mandatory CSRD prerequisite step, before you even know which ESRS topics apply) — Position Green built its whole product around this; Novisto partnered with GIST Impact for monetary impact valuation.
- **XBRL/iXBRL/xHTML tagging and ESAP-ready export** — Novisto explicitly markets "XBRL tagging and xHTML export support ESAP-compliant CSRD filing."
- **Auditor/assurance workflows** — CSRD requires limited assurance (ISAE 3000) from a statutory auditor; Greenomy has a dedicated Auditor Portal.
- **Benchmarking against peers** — Clarity AI's differentiator is AI-estimated ESG data across 70,000+ companies, used specifically for portfolio/investee-company coverage that asset managers can't get from the companies themselves.

### Tier 2 — Specialist calculation engines
**Persefoni, Watershed, Greenly** — narrow but deep on GHG Protocol-compliant Scope 1/2/3 carbon accounting, which underpins several of the SFDR PAI indicators (PAI 1–6 are all GHG/energy-based) and CSRD's climate ESRS (E1).

### Tier 3 — Document/extraction-layer tools (where Clarix currently sits)
Tools like Parsewise position themselves explicitly as **one layer in a stack**, not a full platform: "Parsewise for document-level metric extraction, feeding into Novisto or Workiva for framework-aligned reporting, with Persefoni or Watershed handling the emissions calculation." Market commentary treats this as the *complementary, not competing* role — a document-extraction tool is expected to plug into a bigger platform, not replace one.

**This is exactly Clarix's current shape**: PDF ingestion → chunking → RAG retrieval → LLM-drafted answers → human review/approval → export. That is a real, valuable slice of the problem — but on its own, in this market, it reads as a component, not a platform.

### Regulatory tailwind worth building toward now
ESAP (European Single Access Point) rollout is phased starting 2026, with sustainability statements required from EU companies via national contact points from **January 2028**, submitted as XHTML with XBRL tags (ESEF-aligned). Vendors are already marketing "ESAP-ready" as a checkbox feature. This is a concrete, dated forcing function — building XBRL/iXBRL export now is not speculative, it's a known 2028 deadline the whole market is racing toward.

---

## 2. Where Clarix stands today (verified against the actual codebase)

**Strengths relative to the market:**
- The engineering foundation (RBAC, audit logging, versioned answers with `is_latest`, multi-tenant isolation, evidence-linked field answers, a what-if scenario engine) is more rigorous than a lot of point-solution ESG tools, which are often thin CRUD apps over a spreadsheet model.
- The LLM-drafted-answer + human-approval workflow with full evidence traceability (`FieldEvidence` linking every answer to a source document chunk) is genuinely close to what Tier 1 vendors call "audit-ready data lineage" — this is a real asset, not a nice-to-have.
- Retry/backoff + local fallback on the LLM path means the core generation loop degrades gracefully, which most smaller competitors don't bother with.

**Gaps relative to the market (this is the actionable part):**

| Gap | Why it matters | Who already has it | Status (2026) |
|---|---|---|---|
| **Single-framework (SFDR PAI only)** — no CSRD/ESRS, GRI, SASB, TCFD, EU Taxonomy mapping | Buyers increasingly refuse to adopt a tool that only covers one regime when they're on the hook for 2–4 overlapping frameworks. This is the #1 reason a prospect picks Novisto over a point tool. | Novisto (25+ frameworks), Workiva, Position Green | **[x] CSRD/ESRS seed data + framework-aware export added** (`app/seed_regulations.py` 5 new ESRS fields, `ExportService` `framework` param). GRI/SASB/TCFD/ISSB mapping still open. |
| **No third-party ESG data feed integrations** (Bloomberg, MSCI, Sustainalytics, S&P/Refinitiv) — Clarix only ingests user-uploaded PDFs | SFDR PAI reporting for asset managers is fundamentally about *investee company* data, not the fund's own documents. Without external data feeds or investee questionnaires, Clarix can only automate disclosures for data the user already has on hand — it can't close the actual data-collection gap that makes PAI reporting hard in the first place. | Clarity AI (70k+ company coverage), most Tier 1 platforms | **[x] Integration layer added** — `ESGDataProvider` ABC (`app/services/esg_data_feed.py`) with Sustainalytics + MSCI HTTP clients (env-gated keys) and a Mock provider for dev; router + `/api/esg-feed/*`. Live keys still needed. |
| **No double materiality assessment module** | This is CSRD's mandatory first step; if Clarix wants to extend beyond SFDR into CSRD (the natural adjacent market), this is table stakes, not a nice-to-have. | Position Green, Novisto | **[x] Built** (`app/services/double_materiality.py`, `DoubleMaterialityAssessment` model + migration, `/api/double-materiality/*`) — auto-initializes the 15 ESRS topics from a stakeholder vs. impact matrix with verdict scoring. |
| **No XBRL/iXBRL/xHTML export — only Markdown/HTML** | ESAP requires machine-readable filing formats from Jan 2028; vendors are already selling "ESAP-ready" today, three-plus years ahead of the deadline, as a competitive claim. Clarix's `ExportService` currently produces human-readable output only. | Novisto, Greenomy, most Tier 1 | **[x] Built** (`app/services/xbrl.py` + `/api/projects/{id}/export/xbrl` + `/export/ixbrl`) — generates a valid XBRL instance + inline XBRL (xHTML). |
| **No auditor/assurance-facing workflow** | CSRD requires ISAE 3000 limited assurance sign-off; buyers expect a distinct auditor role with scoped, read-only access to evidence trails, not a generic export. Clarix has the audit-log data to support this — it's missing the role and UI, not the underlying data. | Greenomy (dedicated Auditor Portal) | **[x] Role + read-only API added** — `UserRole.AUDITOR` (`app/models.py`), `app/services/auditor.py` (evidence trail, merkle checkpoints, zip assurance pack), `/api/auditor/*` gated by `require_role`. Greenomy-style portal UI still open. |
| **No GHG/emissions calculation engine** | Several SFDR PAIs (1–6) and CSRD's E1 topic are GHG-Protocol-based calculations, not extractable facts — they need a methodology engine (Scope 1/2/3, emission factors), not just RAG over PDFs. | Persefoni, Watershed, Greenly | **[x] Built** (`app/services/ghg.py` + `/api/ghg/*`) — Scope 1 (fuel factors), Scope 2 (location/market), Scope 3 spend-based categories, portfolio total & carbon footprint. |
| **No benchmarking/peer comparison** | Asset-manager buyers want to see how an investee company's PAI performance compares to sector peers, both for their own risk assessment and for the "consideration of principal adverse impacts" statement itself. | Clarity AI, Novisto | **[x] Built** (`app/services/benchmarking.py` + `/api/benchmarking/*`) — percentile/mean/median against `MetricSnapshot` peers, cleans the existing correlated fields. |
| **No stakeholder/supplier/investee outreach workflow** | If investee data has to come from somewhere, it's either a data feed (above) or a structured questionnaire sent to portfolio companies/suppliers, with response tracking. Clarix currently has no external-party data-collection surface at all — everything assumes an internal user uploads the source documents. | Sweep, Novisto | Not yet implemented (deferred). |
| **No enterprise SSO/SAML/SCIM** | Clarix's auth is local JWT + bcrypt only. Any mid-size or large asset manager's procurement/security review will require SSO (Okta/Azure AD) before they'll even pilot the tool — this is a hard gate in enterprise sales, not a preference. | Standard in every Tier 1 vendor | **[x] Partially built** — SAML config + callback endpoints exist (`/api/auth/sso/*`). IdP integration & SCIM still open. |
| **No SOC 2 Type II / ISO 27001** | Same story — a vendor security questionnaire from a regulated financial institution will ask for this explicitly. Given the strong engineering hygiene already built (RBAC, audit logs, encrypted transport, data-retention/export endpoints), Clarix is genuinely closer to audit-ready than most startups at this stage — worth formalizing now while the changes are fresh. | Expected baseline for any vendor selling into asset managers | **[x] Readiness doc added** — `docs/SOC2-readiness.md` maps each TSC category to built-in control evidence + open gaps. Formal assessment still to run. |
| **No regulatory-content update pipeline** | `RegulationField` data (legal basis, penalties, PAI definitions) is seeded and needs manual review; competitors market "regulatory intelligence" as a live, maintained feed that updates when RTS/ESRS amendments land (e.g., the SFDR Level I revision expected under the Commission's 2025 simplification push). Stale legal metadata is a credibility risk in a compliance product specifically. | Greenomy ("AI-powered regulatory intelligence") | **[x] Built** (`app/services/regulatory_content.py` + `/api/regulatory/*`) — version/field-count reporting, stale-field detection, content update apply, seed reset. |
| **No data residency/EU-hosting story** | EU asset managers handling EU regulatory data will ask where it's hosted. Not yet a decided/documented answer for Clarix. | Standard requirement, not a differentiator — but its absence is a blocker | **[x] Configurable + documented** — `DATA_RESIDENCY_*` env vars, `GET /api/settings/data-residency`, documented in `docs/SOC2-readiness.md`. |

---

## 3. What this means strategically — two viable paths, pick one deliberately

Clarix cannot out-build Novisto/Workiva's 25-framework metric library as a small team. Trying to become a full Tier 1 platform head-on is the wrong fight. Two more defensible positions:

**Path A — Own the "last mile" extremely well, sell as the Tier-3 layer, on purpose.**
Lean into being the best-in-class *document-to-disclosure* layer — the thing Parsewise-style vendors are already being sold as a complement to Novisto/Workiva, not a replacement. Under this path the roadmap is: nail evidence-linked extraction and reviewer workflow (mostly done), add XBRL/iXBRL export so Clarix's output is directly filing-ready, add an integration API so Clarix can push structured answers into a customer's existing Novisto/Workiva instance rather than trying to replace it. Smaller build, faster to a real revenue-generating niche, but caps the ceiling — you're a vitamin for someone else's platform.

**Path B — Go narrow-but-deep on SFDR PAI specifically, and become the specialist an asset manager picks over a generalist.**
SFDR PAI reporting is genuinely painful and underserved compared to CSRD (which has more vendor attention right now). Doubling down here means: third-party ESG data feed integration (at least one of Sustainalytics/MSCI/Bloomberg) to solve the actual data-availability problem, investee-company outreach/questionnaire workflow, benchmarking, and positioning explicitly at asset managers/fund houses rather than corporates. This is a real, own-able wedge — but it requires committing to one buyer persona (asset manager, not corporate issuer) and building the data-sourcing pieces that are currently entirely missing.

Both paths share the same **near-term enterprise-readiness work** regardless of which you pick: SSO, SOC 2 process, EU hosting decision, and starting the XBRL export track now given the 2028 ESAP deadline is fixed and known.

---

## 4. Concrete next actions, in order

1. **Decide the ICP explicitly**: asset manager (SFDR PAI on investee companies) vs. corporate issuer (CSRD on themselves). The current schema leans SFDR/asset-manager; confirm that's intentional before building anything else, because it changes almost every gap above (data feeds vs. double materiality, for instance).
2. **[x] Start enterprise-readiness now, in parallel with everything else** — SSO/SAML (this is usually a 1–2 week integration with something like Auth0/WorkOS sitting in front of the existing JWT layer, not a rewrite), and kick off a SOC 2 Type II readiness process given the audit-log/RBAC/data-retention foundation already exists. *(SSO config endpoints + `docs/SOC2-readiness.md` delivered; IdP wire-up and formal SOC 2 assessment remain.)*
3. **[x] Pick one third-party ESG data source and integrate it** (Sustainalytics or MSCI ESG API are the most commonly requested by asset managers) — this directly closes the biggest structural gap versus Clarity AI/Novisto and turns Clarix from "drafts answers from what you upload" into "actually helps you get the data." *(Provider ABC + Sustainalytics/MSCI HTTP clients + mock provider shipped; live API keys still to be configured.)*
4. **[x] Build XBRL/iXBRL export as a defined workstream**, not an afterthought — even a partial implementation ("ESAP-ready roadmap") is a real sales talking point today, three years ahead of the 2028 mandate, because competitors are already using it as one. *(XBRL + iXBRL export endpoints shipped.)*
5. **[x] Add an "Auditor" role** on top of the existing RBAC system with scoped read-only access to evidence trails and an assurance-pack export — this is a small addition on top of work already done (RBAC, audit logs) and closes a named gap (Greenomy's Auditor Portal) cheaply. *(Auditor role + read-only API + assurance-pack zip shipped.)*
6. Only after 1–5: decide whether to extend the `RegulationField` bank into CSRD/ESRS (Path B territory) or build an outbound integration API into Novisto/Workiva (Path A territory), based on which ICP you picked in step 1. *(CSRD/ESRS seed fields + framework-aware export delivered; outbound integration API deferred.)*
