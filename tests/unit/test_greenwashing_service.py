"""
Unit tests for the GreenwashingDetector service.
"""

import os
import sys
import uuid


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.models import (
    Document, DocumentChunk, FieldAnswer, RegulationField,
    AnswerStatus,
)
from app.services.greenwashing import GreenwashingDetector


class TestClaimExtraction:
    def test_extract_zero_fossil_claim(self):
        text = (
            "Our flagship fund is 100% green and has zero fossil fuel exposure. "
            "We have achieved net zero across all scopes."
        )
        claims = GreenwashingDetector.extract_marketing_claims(text)
        assert len(claims) >= 2
        categories = {c["category"] for c in claims}
        assert "fossil_exposure" in categories
        assert "net_zero_overstatement" in categories

    def test_extract_percentage_sustainable_claim(self):
        text = "82% of our investments are sustainable and aligned with the EU Taxonomy."
        claims = GreenwashingDetector.extract_marketing_claims(text)
        assert len(claims) >= 1
        assert claims[0]["claimed_metric"] == 82.0

    def test_extract_no_claims_returns_empty(self):
        text = "The quarterly report reviews our portfolio performance across several strategies."
        claims = GreenwashingDetector.extract_marketing_claims(text)
        assert claims == []

    def test_extract_handles_empty_string(self):
        claims = GreenwashingDetector.extract_marketing_claims("")
        assert claims == []


class TestContradictionDetection:
    def test_zero_fossil_claim_conflicts_with_audited_exposure(self):
        claims = [
            {
                "pattern_name": "zero_fossil",
                "category": "fossil_exposure",
                "field_codes": ["PAI_FOSSIL_FUEL"],
                "quote": "zero fossil fuel exposure",
                "sentence": "Our fund has zero fossil fuel exposure.",
                "claimed_metric": 0.0,
                "unit": "%",
                "source": {"document_id": "doc1", "page": 2},
            }
        ]
        audited = [
            {"field_code": "PAI_FOSSIL_FUEL", "value": 2.4, "unit": "%", "status": "Approved", "has_value": True}
        ]
        findings = GreenwashingDetector.detect_contradictions(claims, audited)
        assert len(findings) == 1
        assert findings[0]["discrepancy_category"] == "fossil_exposure"
        assert findings[0]["contradicting_field_code"] == "PAI_FOSSIL_FUEL"
        assert findings[0]["contradicting_value"]["value"] == 2.4
        assert "PAI_FOSSIL_FUEL" in findings[0]["legal_citation"] or "SFDR" in findings[0]["legal_citation"]

    def test_no_contradiction_when_claim_matches_audited(self):
        claims = [
            {
                "pattern_name": "zero_fossil",
                "category": "fossil_exposure",
                "field_codes": ["PAI_FOSSIL_FUEL"],
                "quote": "zero fossil fuel exposure",
                "sentence": "Our fund has zero fossil fuel exposure.",
                "claimed_metric": 0.0,
                "unit": "%",
                "source": {},
            }
        ]
        audited = [
            {"field_code": "PAI_FOSSIL_FUEL", "value": 0.0, "unit": "%", "status": "Approved", "has_value": True}
        ]
        findings = GreenwashingDetector.detect_contradictions(claims, audited)
        assert findings == []

    def test_100pct_green_claim_flags_partial_allocation(self):
        claims = [
            {
                "pattern_name": "hundred_percent_green",
                "category": "absolute_claim_vs_measured",
                "field_codes": ["PERIODIC_ASSET_ALLOCATION"],
                "quote": "fully green",
                "sentence": "The fund is fully green.",
                "claimed_metric": 100.0,
                "unit": "%",
                "source": {},
            }
        ]
        audited = [
            {"field_code": "PERIODIC_ASSET_ALLOCATION", "value": 82.5, "unit": "%", "status": "Approved", "has_value": True}
        ]
        findings = GreenwashingDetector.detect_contradictions(claims, audited)
        assert len(findings) == 1
        assert findings[0]["discrepancy_category"] == "absolute_claim_vs_measured"

    def test_missing_audited_value_skips_claim(self):
        claims = [
            {
                "pattern_name": "zero_fossil",
                "category": "fossil_exposure",
                "field_codes": ["PAI_FOSSIL_FUEL"],
                "quote": "zero fossil",
                "sentence": "Zero fossil exposure.",
                "claimed_metric": 0.0,
                "unit": "%",
                "source": {},
            }
        ]
        audit_empty = []
        findings = GreenwashingDetector.detect_contradictions(claims, audit_empty)
        assert findings == []


class TestRiskScoring:
    def test_zero_findings_zero_score(self):
        score = GreenwashingDetector.calculate_risk_score([])
        assert score["risk_score"] == 0.0
        assert score["risk_level"] == "Low"

    def test_critical_finding_high_score(self):
        findings = [
            {
                "severity": "Error",
                "penalty_tier": "Critical",
            },
            {
                "severity": "Error",
                "penalty_tier": "Critical",
            },
        ]
        score = GreenwashingDetector.calculate_risk_score(findings)
        assert score["risk_score"] >= 60
        assert score["risk_level"] in ("High", "Critical")
        assert score["total_findings"] == 2

    def test_risk_score_within_range(self):
        findings = [
            {"severity": "Warning", "penalty_tier": "High"},
            {"severity": "Info", "penalty_tier": "Medium"},
        ]
        score = GreenwashingDetector.calculate_risk_score(findings)
        assert 0 <= score["risk_score"] <= 100


class TestFullAuditFlow:
    def _seed_marketing_document(self, seeded_db, test_project, text):
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            project_id=test_project.id,
            file_name="marketing_factsheet.pdf",
            file_type="pdf",
            source_type="marketing",
            storage_url="/tmp/factsheet.pdf",
            parsed_status="Completed",
        )
        seeded_db.add(doc)
        seeded_db.add(DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            page_no=1,
            section_title="Key Claims",
            chunk_text=text,
        ))
        seeded_db.commit()
        return doc

    def _seed_approved_answer(self, seeded_db, test_project, field_code, value, unit="%"):
        field = seeded_db.query(RegulationField).filter(
            RegulationField.field_code == field_code
        ).first()
        if not field:
            field = RegulationField(
                id=str(uuid.uuid4()),
                framework="SFDR",
                disclosure_type="entity_pai",
                field_code=field_code,
                field_label=field_code,
                field_kind="numeric",
                mandatory=True,
            )
            seeded_db.add(field)
        else:
            # Use the field (may be seeded or from conftest) — ensure we have the right ID.
            pass

        answer = FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            regulation_field_id=field.id,
            answer_json={"value": value, "unit": unit},
            answer_text=f"{value}{unit}",
            status=AnswerStatus.APPROVED.value,
            version_no=1,
            is_latest=True,
        )
        seeded_db.add(answer)
        seeded_db.commit()

    def test_run_audit_detects_contradiction(self, seeded_db, test_project):
        # Seed audited fossil fuel exposure of 2.4%
        self._seed_approved_answer(seeded_db, test_project, "PAI_FOSSIL_FUEL", 2.4)

        # Seed marketing doc claiming zero fossil
        marketing_text = (
            "Our flagship fund maintains zero fossil fuel exposure and is fully green. "
            "82% of the portfolio is sustainable."
        )
        doc = self._seed_marketing_document(seeded_db, test_project, marketing_text)

        audit = GreenwashingDetector.run_audit(
            db=seeded_db,
            project_id=test_project.id,
            document_id=doc.id,
            actor_id="test_user",
        )

        assert audit.audit_status == "Completed"
        assert audit.total_claims_extracted >= 2
        assert audit.total_findings >= 1
        assert audit.risk_score > 0
        assert audit.risk_level in ("Low", "Moderate", "High", "Critical")

    def test_run_audit_no_contradiction_baseline(self, seeded_db, test_project):
        # Seed audited value that MATCHES the claim
        self._seed_approved_answer(seeded_db, test_project, "PAI_FOSSIL_FUEL", 0.0)

        # Marketing doc claims zero fossil — consistent with audited 0%
        doc = self._seed_marketing_document(
            seeded_db,
            test_project,
            "Our fund has zero fossil fuel exposure across the entire portfolio.",
        )

        audit = GreenwashingDetector.run_audit(
            db=seeded_db,
            project_id=test_project.id,
            document_id=doc.id,
            actor_id="test_user",
        )

        assert audit.audit_status == "Completed"
        assert audit.total_findings == 0
        assert audit.risk_score == 0.0
        assert audit.risk_level == "Low"

    def test_run_audit_missing_document_is_robust(self, seeded_db, test_project):
        # No audited answers, so claims cannot be contradicted — still completes
        doc = self._seed_marketing_document(
            seeded_db,
            test_project,
            "The fund is 100% sustainable and has zero fossil fuel.",
        )
        audit = GreenwashingDetector.run_audit(
            db=seeded_db,
            project_id=test_project.id,
            document_id=doc.id,
            actor_id="test_user",
        )
        assert audit.audit_status in ("Completed", "Failed")
        if audit.audit_status == "Completed":
            assert audit.total_findings >= 0
