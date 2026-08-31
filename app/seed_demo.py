"""
Demo data seed script for the Clarix compliance workspace.

Populates a realistic, end-to-end demonstration dataset under the default
organization so that logging in as `system@sfdr.ai` (System Auto-Agent)
shows populated projects, compliance matrices, greenwashing findings,
cross-framework harmonization, what-if scenarios, audit trails, and more.

Idempotent: safe to run multiple times. Uses the app's own services where
possible (greenwashing detector, cross-framework harmonizer, what-if engine,
intake service) so the seeded data matches exactly what those features produce.
"""
import datetime
import logging
import uuid

from app.database import SessionLocal
from app.models import (
    Organization, User, Product, ReportingProject, Document, DocumentChunk,
    RegulationField, FieldAnswer, FieldEvidence, AuditLog,
    MetricSnapshot, AnswerStatus, ProjectStatus,
)

from app.services.greenwashing import GreenwashingDetector
from app.services.what_if_engine import WhatIfEngine
from app.services.intake import DataIntakeService

logger = logging.getLogger("app.seed_demo")

ORG_ID = "default_org"

# Scenario dates for the 2025 reporting cycle
PERIOD_START = datetime.date(2025, 1, 1)
PERIOD_END = datetime.date(2025, 12, 31)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_field(db, field_code):
    return db.query(RegulationField).filter(RegulationField.field_code == field_code).first()


def _upsert_project(db, project_id, name, disclosure_type, status, sector=None, product_id=None):
    proj = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if proj:
        return proj
    proj = ReportingProject(
        id=project_id,
        organization_id=ORG_ID,
        product_id=product_id,
        name=name,
        disclosure_type=disclosure_type,
        reporting_period_start=PERIOD_START,
        reporting_period_end=PERIOD_END,
        status=status,
        reporting_year=2025,
        industry_sector=sector,
    )
    db.add(proj)
    db.flush()
    return proj


def _ensure_baseline_answers(db, project, disclosure_type, framework="SFDR"):
    """Create a MISSING baseline answer for every field of a disclosure type absent an answer."""
    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == disclosure_type,
        RegulationField.framework == framework,
    ).all()
    existing = {
        a.regulation_field_id
        for a in db.query(FieldAnswer).filter(FieldAnswer.project_id == project.id).all()
    }
    for field in fields:
        if field.id in existing:
            continue
        db.add(FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=project.id,
            regulation_field_id=field.id,
            status=AnswerStatus.MISSING.value,
            answer_text="",
            version_no=1,
            is_latest=True,
            regulation_version=field.regulation_version,
        ))
    db.flush()


def _existing_answer(db, project, field):
    """Latest answer row for a project/field, if any (across versions)."""
    return db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project.id,
        FieldAnswer.regulation_field_id == field.id,
    ).order_by(FieldAnswer.version_no.desc()).first()


def _set_approved_answer(db, project, field_code, value, unit, answer_text, approved_by_id="user_admin"):
    field = _get_field(db, field_code)
    if not field:
        logger.warning("Field %s not found; skipping", field_code)
        return None
    ans = _existing_answer(db, project, field)
    data = {
        "answer_json": {"value": value, "unit": unit},
        "answer_text": answer_text,
        "status": AnswerStatus.APPROVED.value,
        "model_name": "demo_seed",
        "regulation_version": field.regulation_version,
        "approved_by": approved_by_id,
        "is_latest": True,
    }
    if ans:
        for k, v in data.items():
            setattr(ans, k, v)
        db.flush()
        return ans
    ans = FieldAnswer(
        id=str(uuid.uuid4()),
        project_id=project.id,
        regulation_field_id=field.id,
        version_no=1,
        **data,
    )
    db.add(ans)
    db.flush()
    return ans


def _set_draft_answer(db, project, field_code, value, unit, answer_text, model_name="demo_seed"):
    field = _get_field(db, field_code)
    if not field:
        return None
    ans = _existing_answer(db, project, field)
    data = {
        "answer_json": {"value": value, "unit": unit},
        "answer_text": answer_text,
        "status": AnswerStatus.DRAFT.value,
        "model_name": model_name,
        "regulation_version": field.regulation_version,
        "is_latest": True,
    }
    if ans:
        for k, v in data.items():
            setattr(ans, k, v)
        db.flush()
        return ans
    ans = FieldAnswer(
        id=str(uuid.uuid4()),
        project_id=project.id,
        regulation_field_id=field.id,
        version_no=1,
        is_latest=True,
        **data,
    )
    db.add(ans)
    db.flush()
    return ans


def _add_evidence(db, project, field_code, value, unit, confidence, chunk_id=None, method="hybrid_retrieval",
                  source_locator=None):
    field = _get_field(db, field_code)
    if not field:
        return
    existing = None
    q = db.query(FieldEvidence).filter(
        FieldEvidence.project_id == project.id,
        FieldEvidence.regulation_field_id == field.id,
        FieldEvidence.extraction_method == method,
    )
    if chunk_id is not None:
        q = q.filter(FieldEvidence.document_chunk_id == chunk_id)
    else:
        q = q.filter(FieldEvidence.document_chunk_id.is_(None))
    existing = q.first()
    if existing:
        return
    db.add(FieldEvidence(
        id=str(uuid.uuid4()),
        project_id=project.id,
        regulation_field_id=field.id,
        document_chunk_id=chunk_id,
        source_locator=source_locator or {"page": 1},
        extracted_value={"value": value, "unit": unit},
        confidence=confidence,
        extraction_method=method,
    ))
    db.flush()


def _add_document(db, project, doc_id, file_name, file_type, source_type, parsed_status="Completed"):
    existing = db.query(Document).filter(Document.id == doc_id).first()
    if existing:
        return existing
    doc = Document(
        id=doc_id,
        project_id=project.id,
        file_name=file_name,
        file_type=file_type,
        source_type=source_type,
        storage_url=f"/demo/storage/{doc_id}.{file_type}",
        parsed_status=parsed_status,
    )
    db.add(doc)
    db.flush()
    return doc


def _add_chunk(db, document, chunk_id, page_no, section_title, chunk_text):
    existing = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
    if existing:
        return
    db.add(DocumentChunk(
        id=chunk_id,
        document_id=document.id,
        page_no=page_no,
        section_title=section_title,
        chunk_text=chunk_text,
        chunk_hash=uuid.uuid4().hex,
    ))
    db.flush()


def _add_audit_log(db, project, entity_type, entity_id, action, actor_id, payload=None):
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        project_id=project.id,
        payload=payload or {},
    ))
    db.flush()


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
DEMO_PROJECT_IDS = ["prj_art8", "prj_art9", "prj_pai"]


def _cleanup_prior_demo(db):
    """Remove artifacts from a previous demo-seed run so re-seeding is clean."""
    from app.models import WhatIfScenario, DataIntakeRequest, GreenwashingAudit
    for pid in DEMO_PROJECT_IDS:
        # Greenwashing audits for demo projects (and cascade findings)
        for gw in db.query(GreenwashingAudit).filter(GreenwashingAudit.project_id == pid).all():
            db.delete(gw)
        # What-if scenarios created by the demo
        for sc in db.query(WhatIfScenario).filter(WhatIfScenario.project_id == pid).all():
            db.delete(sc)
        # Data intake requests created by the demo
        for req in db.query(DataIntakeRequest).filter(DataIntakeRequest.project_id == pid).all():
            db.delete(req)
        # Harmonized draft answers created by the harmonizer on the PAI project
    pp = db.query(ReportingProject).filter(ReportingProject.id == "prj_pai").first()
    if pp:
        for ans in db.query(FieldAnswer).filter(
            FieldAnswer.project_id == pp.id,
            FieldAnswer.model_name == "cross_framework_harmonizer",
        ).all():
            db.delete(ans)
    db.flush()


def seed_demo(db=None):
    """Seed the demo dataset. Idempotent. Returns a summary dict."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    summary = {"projects": {}, "greenwashing_findings": 0, "harmonized": 0, "scenarios": 0}

    try:
        _cleanup_prior_demo(db)
        db.flush()

        # --- 0. Ensure organization & associate demo users to it -----------------
        org = db.query(Organization).filter(Organization.id == ORG_ID).first()
        if not org:
            org = Organization(id=ORG_ID, name="Greenfield Capital Partners Ltd", type="Asset Manager")
            db.add(org)
        else:
            org.name = org.name or "Greenfield Capital Partners Ltd"
            org.type = org.type or "Asset Manager"

        for user_id in ["system", "user_officer", "user_reviewer", "user_admin"]:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.organization_id = ORG_ID
        # Also attach any users created via the UI that have no org
        for user in db.query(User).filter(User.organization_id.is_(None)).all():
            user.organization_id = ORG_ID
        db.flush()

        # --- 1. Products ---------------------------------------------------------
        products = {
            "prod_8": ("GreenFuture Global Equity Fund", "Article 8"),
            "prod_9": ("NetZero Alpha Fund", "Article 9"),
            "prod_pai": ("Greenfield Enterprise (Entity-Level PAI)", "Article 8"),
        }
        prod_ids = {}
        for pid, (name, article) in products.items():
            prod = db.query(Product).filter(Product.id == pid).first()
            if not prod:
                prod = Product(id=pid, organization_id=ORG_ID, name=name, sfdr_article=article, active=True)
                db.add(prod)
                db.flush()
            prod_ids[pid] = prod.id

        # =====================================================================
        # PROJECT 1 — Article 8 Periodic (fully filed / Completed)
        # =====================================================================
        p8 = _upsert_project(db, "prj_art8",
                             "GreenFuture Global Equity Fund — 2025 Periodic (Article 8)",
                             "periodic", ProjectStatus.COMPLETED.value,
                             sector="Investment Funds", product_id=prod_ids["prod_8"])
        _ensure_baseline_answers(db, p8, "periodic")

        _set_approved_answer(db, p8, "PERIODIC_ASSET_ALLOCATION", 78.5, "%",
                             "78.5% of the fund's assets are invested in sustainability-related investments within the meaning of SFDR Art. 2(17).")
        _set_approved_answer(db, p8, "PERIODIC_TAXONOMY_ALIGNMENT", 45.2, "%",
                             "45.2% of underlying investments are taxonomy-aligned activities under the EU Taxonomy Regulation.")
        _set_approved_answer(db, p8, "PERIODIC_SOCIAL_OBJECTIVE", 12.0, "%",
                             "12.0% of investments are made in socially sustainable investments contributing to social objectives.")
        _set_approved_answer(db, p8, "PERIODIC_SUSTAIN_INVEST_TARGET", None, None,
                             "The fund invests with the aim of achieving a sustainable investment objective primarily through its environmental characteristics: climate change mitigation and adaptation. Progress is measured against the fund's SFDR Art. 9 objective roadmap.")
        _add_evidence(db, p8, "PERIODIC_ASSET_ALLOCATION", 78.5, "%", 0.97, method="llm",
                      source_locator={"page": 12, "file": "greenfuture_annual_report.pdf"})

        doc81 = _add_document(db, p8, "doc_art8_sustainability", "GreenFuture_Annual_Sustainability_2025.pdf", "pdf",
                              "sustainability_report")
        _add_chunk(db, doc81, "chunk_art8_1", 12, "Sustainable Investment Objective",
                   "78.5% of aggregate assets are invested in sustainability-related investments, of which 45.2% are EU taxonomy-aligned, consistent with the fund's Article 8 characteristics.")
        _add_evidence(db, p8, "PERIODIC_TAXONOMY_ALIGNMENT", 45.2, "%", 0.95, chunk_id="chunk_art8_1", method="hybrid_retrieval",
                      source_locator={"page": 12, "file": "GreenFuture_Annual_Sustainability_2025.pdf"})

        _add_audit_log(db, p8, "project", p8.id, "create", "system", {"name": p8.name})
        _add_audit_log(db, p8, "answer", "PERIODIC_ASSET_ALLOCATION", "approve", "user_admin",
                       {"field": "PERIODIC_ASSET_ALLOCATION", "action": "approved"})
        summary["projects"]["prj_art8"] = "Article 8 periodic (completed)"

        # =====================================================================
        # PROJECT 2 — Article 9 Periodic (greenwashing demo / Validating)
        # =====================================================================
        p9 = _upsert_project(db, "prj_art9",
                             "NetZero Alpha Fund — 2025 Periodic (Article 9)",
                             "periodic", ProjectStatus.VALIDATING.value,
                             sector="Investment Funds", product_id=prod_ids["prod_9"])
        _ensure_baseline_answers(db, p9, "periodic")

        _set_approved_answer(db, p9, "PERIODIC_ASSET_ALLOCATION", 92.0, "%",
                             "92.0% of assets are invested in sustainable investments with an environmental objective.")
        _set_approved_answer(db, p9, "PERIODIC_TAXONOMY_ALIGNMENT", 61.0, "%",
                             "61.0% of investments are taxonomy-aligned.")
        _set_approved_answer(db, p9, "PERIODIC_SOCIAL_OBJECTIVE", 8.0, "%",
                             "8.0% of investments contribute to social objectives.")
        _set_approved_answer(db, p9, "PERIODIC_SUSTAIN_INVEST_TARGET", None, None,
                             "The fund pursues a sustainable investment objective aligned with the Paris Agreement, targeting net zero by 2050 with interim 2030 milestones.")
        _set_approved_answer(db, p9, "PAI_GHG_SCOPE1", 12400.0, "tCO2e",
                             "Portfolio-weighted Scope 1 GHG emissions of 12,400 tCO2e.")
        _set_approved_answer(db, p9, "PAI_GHG_SCOPE2", 5630.0, "tCO2e",
                             "Portfolio-weighted Scope 2 GHG emissions of 5,630 tCO2e.")
        _set_approved_answer(db, p9, "PAI_GHG_SCOPE3", 78200.0, "tCO2e",
                             "Portfolio-weighted Scope 3 GHG emissions of 78,200 tCO2e.")
        _add_evidence(db, p9, "PAI_GHG_SCOPE1", 12400.0, "tCO2e", 0.96, method="llm",
                      source_locator={"page": 8, "file": "netzero_alpha_annual_report.pdf"})

        # Audited report + marketing document (for greenwashing scan)
        doc_audited = _add_document(db, p9, "doc_art9_audited", "NetZero_Alpha_Audited_2025.pdf", "pdf", "annual_report")
        # Marketing / factsheet with exaggerated claims
        doc_mkt = _add_document(db, p9, "doc_art9_marketing", "NetZeroAlpha_Fund_Factsheet_Q4.pdf", "pdf", "factsheet",
                                parsed_status="Completed")
        marketing_text = (
            "The NetZero Alpha Fund is 100% green and fully aligned with the EU Taxonomy. "
            "We hold zero fossil fuel assets across the entire portfolio. "
            "The fund is already net zero and carbon neutral across all emissions scopes. "
            "Every investment is entirely sustainable and contributes to a 100% green economy."
        )
        _add_chunk(db, doc_mkt, "chunk_art9_mkt_1", 1, "Fund Factsheet Highlights", marketing_text)
        _add_chunk(db, doc_audited, "chunk_art9_aud_1", 8, "PAI Indicators",
                   "Portfolio exhibits 4.2% fossil fuel exposure with GHG intensity above EU average.")
        _add_evidence(db, p9, "PAI_FOSSIL_FUEL", 4.2, "%", 0.93, chunk_id="chunk_art9_aud_1", method="hybrid_retrieval",
                      source_locator={"page": 8, "file": "NetZero_Alpha_Audited_2025.pdf"})

        # Create baseline answers for PAI fields used by greenwashing
        _ensure_baseline_answers(db, p9, "entity_pai")

        _add_audit_log(db, p9, "document", doc_mkt.id, "upload", "user_officer", {"file": doc_mkt.file_name})
        summary["projects"]["prj_art9"] = "Article 9 periodic (validating, greenwashing demo)"

        # =====================================================================
        # PROJECT 3 — Entity/Legal PAI (cross-framework harmony demo)
        # =====================================================================
        pp = _upsert_project(db, "prj_pai",
                             "Greenfield Enterprise — 2025 Entity-Level PAI",
                             "entity_pai", ProjectStatus.REVIEWED.value,
                             sector="Financial Services", product_id=prod_ids["prod_pai"])
        _ensure_baseline_answers(db, pp, "entity_pai")

        # Populate source SFDR answers (approved)
        _set_approved_answer(db, pp, "PAI_GHG_SCOPE1", 31250.0, "tCO2e",
                             "Consolidated Scope 1 GHG emissions of 31,250 tCO2e.")
        _set_approved_answer(db, pp, "PAI_GHG_SCOPE2", 18400.0, "tCO2e",
                             "Consolidated Scope 2 GHG emissions of 18,400 tCO2e (location-based).")
        _set_approved_answer(db, pp, "PAI_GHG_SCOPE3", 402000.0, "tCO2e",
                             "Consolidated Scope 3 GHG emissions of 402,000 tCO2e (category 11: invested assets).")
        _set_approved_answer(db, pp, "PAI_CARBON_FOOTPRINT", 284.3, "tCO2e/EURm",
                             "Carbon footprint of 284.3 tCO2e per EUR million of invested assets.")
        _set_approved_answer(db, pp, "PAI_FOSSIL_FUEL", 3.8, "%",
                             "3.8% portfolio exposure to companies active in the fossil fuel sector.")
        _set_approved_answer(db, pp, "PAI_WATER_EMISSIONS", 42.6, "t/m3",
                             "Tonnes of emissions to water of 42.6 tonnes per million invested.")
        _set_approved_answer(db, pp, "PAI_BOARD_GENDER_DIVERSITY", 34.0, "%",
                             "Board gender diversity of 34% female board members.")
        for code in ["PAI_GHG_SCOPE1", "PAI_GHG_SCOPE2", "PAI_GHG_SCOPE3"]:
            _add_evidence(db, pp, code, 31250.0 if code == "PAI_GHG_SCOPE1" else 18400.0 if code == "PAI_GHG_SCOPE2" else 402000.0,
                          "tCO2e", 0.95, method="llm", source_locator={"page": 5, "file": "greenfield_esg_dataset.xlsx"})

        doc_pai = _add_document(db, pp, "doc_pai_esg", "Greenfield_ESG_Data_2025.xlsx", "xlsx", "policy")
        _add_chunk(db, doc_pai, "chunk_pai_1", 1, "Entity PAI Dataset",
                   "Consolidated entity-level PAI indicators for the 2025 reporting period as reported under SFDR Annex I Table 1.")

        # ---- Cross-framework coverage: seed approved answers for each target
        # framework so the multi-jurisdiction summary shows strong alignment.
        # (The harmonizer would map many SFDR fields onto the same CSRD GHG field,
        # so we seed target answers directly for a clean, re-runnable demo.)
        # CSRD
        _set_approved_answer(db, pp, "CSRD_GHG_SCOPE1", 351900.0, "tCO2e",
                             "CSRD ESRS E1 GHG emissions across all scopes (strictly abated).")
        _set_approved_answer(db, pp, "CSRD_WATER_USE", 42.6, "m3",
                             "CSRD ESRS E3 water consumption of 42.6 thousand m3.")
        _set_approved_answer(db, pp, "CSRD_GENDER_PAY_GAP", 4.5, "%",
                             "CSRD ESRS S1 mean gender pay gap of 4.5%.")
        _set_approved_answer(db, pp, "CSRD_GOVERNANCE_BOARD", 34.0, "%",
                             "CSRD ESRS G1 board composition with 34% female representation.")
        _set_approved_answer(db, pp, "CSRD_BIODIVERSITY", None, None,
                             "CSRD ESRS E4 biodiversity impact assessment completed; no material negative impacts identified in operating footprint.")
        for code in ["CSRD_GHG_SCOPE1", "CSRD_WATER_USE", "CSRD_GENDER_PAY_GAP"]:
            _add_evidence(db, pp, code, 351900.0 if code == "CSRD_GHG_SCOPE1" else 42.6 if code == "CSRD_WATER_USE" else 4.5,
                          "tCO2e" if code == "CSRD_GHG_SCOPE1" else "m3" if code == "CSRD_WATER_USE" else "%",
                          0.94, method="hybrid_retrieval", source_locator={"page": 5, "file": "greenfield_esg_dataset.xlsx"})

        # SEC
        _set_approved_answer(db, pp, "SEC_GHG_SCOPE1", 31250.0, "tCO2e",
                             "SEC Climate Rule Scope 1 GHG emissions (17 CFR 229.1500).")
        _set_approved_answer(db, pp, "SEC_GHG_SCOPE2", 18400.0, "tCO2e",
                             "SEC Climate Rule Scope 2 GHG emissions.")
        _set_approved_answer(db, pp, "SEC_GHG_SCOPE3", 402000.0, "tCO2e",
                             "SEC Climate Rule Scope 3 GHG emissions.")
        _set_approved_answer(db, pp, "SEC_CLIMATE_RISK", None, None,
                             "Climate-related risk management process integrated into enterprise risk committee, covering physical and transition risks.")
        _set_approved_answer(db, pp, "SEC_FINANCIAL_IMPACT", 12.4, "EURm",
                             "Financial impact of climate events estimated at EUR 12.4m for the reporting period.")

        # UK SDR (entity-level metric only; periodic label/policy fields left as
        # gaps so the cross-framework summary realistically shows partial coverage)
        _set_approved_answer(db, pp, "UKSDR_GHG_EMISSIONS", 402000.0, "tCO2e",
                             "UK SDR sustainability objective GHG metric across the portfolio.")

        # ISSB
        _set_approved_answer(db, pp, "ISSB_S2_GHG", 351900.0, "tCO2e",
                             "IFRS S2 GHG emissions (Scope 1, 2, 3) disclosed in accordance with ISSB S2.")
        _set_approved_answer(db, pp, "ISSB_S2_TARGETS", None, None,
                             "Climate targets: 42% reduction in Scope 1 & 2 by 2030, net-zero commitment by 2050 with interim milestones.")
        _set_approved_answer(db, pp, "ISSB_S2_TRANSITION", None, None,
                             "Transition plan aligned with ISSB S2; governed by the board with annual progress review.")
        _set_approved_answer(db, pp, "ISSB_S1_MATERIALITY", None, None,
                             "Materiality assessment under IFRS S1 covering climate, biodiversity, and social matters.")
        _set_approved_answer(db, pp, "ISSB_S1_GOODS_SERVICES", 12.4, "EURm",
                             "Financial effects of climate-related risks estimated at EUR 12.4m.")

        _add_audit_log(db, pp, "project", pp.id, "create", "system", {"name": pp.name})
        summary["projects"]["prj_pai"] = "Entity PAI (multi-framework alignment demo)"

        # =====================================================================
        # Greenwashing audit (Phase 1) on the Article 9 project
        # =====================================================================
        try:
            gw_audit = GreenwashingDetector.run_audit(
                db=db, project_id=p9.id, document_id=doc_mkt.id, actor_id="user_officer",
            )
            summary["greenwashing_risk"] = gw_audit.risk_score
            summary["greenwashing_level"] = gw_audit.risk_level
            summary["greenwashing_findings"] = gw_audit.total_findings
        except Exception as e:
            logger.warning("Greenwashing seed audit failed (robust): %s", e)

        # =====================================================================
        # What-if scenarios (simulator)
        # =====================================================================
        for name, desc, params in [
            ("Scope 3 Removal", "What if we fail to disclose Scope 3 emissions this cycle?",
             {"action": "remove_field", "field_code": "PAI_GHG_SCOPE3"}),
            ("Board Diversity Drop", "Simulate board gender diversity dropping to 28%.",
             {"action": "threshold_change", "field_code": "PAI_BOARD_GENDER_DIVERSITY", "new_value": 28, "threshold": 30}),
            ("Article 9 -> Article 8", "Simulate reclassifying NetZero Alpha from Article 9 to Article 8.",
             {"action": "reclassify_article", "from_article": "Article 9", "to_article": "Article 8"}),
        ]:
            try:
                WhatIfEngine.run_scenario(
                    db=db, project_id=p9.id,
                    scenario_name=name, scenario_description=desc,
                    parameters=params, user_id="user_officer",
                )
                summary["scenarios"] += 1
            except Exception as e:
                logger.warning("What-if seed failed: %s", e)

        # =====================================================================
        # Data intake request (investee portal)
        # =====================================================================
        try:
            DataIntakeService.create_request(
                db=db,
                project_id=pp.id,
                organization_id=ORG_ID,
                target_company_name="SolarEdge Manufacturing GmbH",
                target_company_email="data@solarede-gmbh.de",
                requested_framework="SFDR",
                requested_field_codes=["PAI_GHG_SCOPE1", "PAI_GHG_SCOPE2", "PAI_GHG_SCOPE3", "PAI_FOSSIL_FUEL"],
                expiry_days=30,
                created_by_user_id="user_officer",
            )
            summary["intake_request"] = "created"
        except Exception as e:
            logger.warning("Intake seed failed: %s", e)

        # =====================================================================
        # Metric snapshots (trend dashboard) — 3 years of PAI GHG trends
        # =====================================================================
        ghg_field = _get_field(db, "PAI_GHG_SCOPE1")
        if ghg_field:
            for year, val in [(2023, 34800.0), (2024, 33000.0), (2025, 31250.0)]:
                existing = db.query(MetricSnapshot).filter(
                    MetricSnapshot.organization_id == ORG_ID,
                    MetricSnapshot.regulation_field_id == ghg_field.id,
                    MetricSnapshot.reporting_year == year,
                ).first()
                if existing:
                    continue
                db.add(MetricSnapshot(
                    id=str(uuid.uuid4()),
                    organization_id=ORG_ID,
                    regulation_field_id=ghg_field.id,
                    reporting_year=year,
                    value_numeric=val,
                    value_unit="tCO2e",
                    intensity_denominator=2500.0,
                    intensity_value=val / 2500.0,
                    source_project_id=pp.id,
                ))
            summary["metric_snapshots"] = 3
        db.flush()

        db.commit()

        # Re-validate the PAI project so validation results are populated
        try:
            from app.services.validation import ValidationService
            ValidationService.validate_project(db, pp.id)
            ValidationService.validate_project(db, p8.id)
            db.commit()
        except Exception as e:
            logger.warning("Validation seed failed (robust): %s", e)

        logger.info("Demo seed complete: %s", summary)
        return summary
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = seed_demo()
    import json
    print("=== DEMO SEED SUMMARY ===")
    print(json.dumps(result, indent=2, default=str))
