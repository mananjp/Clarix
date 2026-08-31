"""
Unit tests for the CrossFrameworkTranslator service.
"""

import os
import sys
import uuid


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.models import (
    RegulationField, FieldAnswer, AnswerStatus,
)
from app.services.cross_framework import CrossFrameworkTranslator, SUPPORTED_FRAMEWORKS


def _add_field(db, field_code, framework, field_label, mandatory=True, cross_refs=None, field_kind="numeric"):
    existing = db.query(RegulationField).filter(RegulationField.field_code == field_code).first()
    if existing:
        existing.framework = framework
        existing.field_label = field_label
        existing.mandatory = mandatory
        existing.cross_references = cross_refs
        existing.field_kind = field_kind
        db.flush()
        return existing

    f = RegulationField(
        id=str(uuid.uuid4()),
        framework=framework,
        disclosure_type="entity_pai",
        field_code=field_code,
        field_label=field_label,
        field_kind=field_kind,
        mandatory=mandatory,
        cross_references=cross_refs,
        regulation_version="2024",
    )
    db.add(f)
    db.flush()
    return f


def _add_answer(db, project, field, value=None, unit=None, status=AnswerStatus.APPROVED.value, answer_text=None):
    a = FieldAnswer(
        id=str(uuid.uuid4()),
        project_id=project.id,
        regulation_field_id=field.id,
        answer_json={"value": value, "unit": unit},
        answer_text=answer_text or f"{value}{unit or ''}",
        status=status,
        version_no=1,
        is_latest=True,
    )
    db.add(a)
    db.flush()
    return a


# Custom unique field codes to avoid collision with conftest-seeded fields
# (conftest seeds: PAI_GHG_SCOPE1, PAI_GHG_SCOPE2, PAI_FOSSIL_FUEL)
SRC_GHG_CODE = "TEST_SFDR_GHG"
SRC_FF_CODE = "TEST_SFDR_FOSSIL"
SEC_GHG_CODE = "TEST_SEC_GHG"
UKSDR_GHG_CODE = "TEST_UKSDR_GHG"
ISSB_GHG_CODE = "TEST_ISSB_GHG"


class TestResolveEquivalences:
    def test_resolves_cross_framework_mappings(self, seeded_db, test_project):
        # SFDR field with cross-refs to SEC and UK SDR
        _add_field(
            seeded_db, SRC_GHG_CODE, "SFDR", "Test Scope 1 GHG Emissions",
            cross_refs=[
                {"framework": "SEC", "field_code": SEC_GHG_CODE, "relationship": "equivalent_disclosure"},
                {"framework": "UK SDR", "field_code": UKSDR_GHG_CODE, "relationship": "equivalent_disclosure"},
            ],
        )
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1")
        _add_field(seeded_db, UKSDR_GHG_CODE, "UK SDR", "Test UK GHG metric")
        seeded_db.commit()

        equivalences = CrossFrameworkTranslator.resolve_equivalences(seeded_db, test_project.id)
        assert len(equivalences) >= 2
        eq = [e for e in equivalences if e["source_field_code"] == SRC_GHG_CODE]
        assert len(eq) == 2
        frameworks = {e["target_framework"] for e in eq}
        assert "SEC" in frameworks
        assert "UK SDR" in frameworks

    def test_empty_db_returns_empty(self, db_session, test_project):
        equivalences = CrossFrameworkTranslator.resolve_equivalences(db_session, test_project.id)
        assert equivalences == []


class TestGapDetection:
    def test_detects_missing_mandatory_fields(self, seeded_db, test_project):
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1", mandatory=True)
        seeded_db.commit()

        gaps = CrossFrameworkTranslator.detect_gaps(seeded_db, test_project.id)
        assert any(g["field_code"] == SEC_GHG_CODE for g in gaps)
        assert all(g["missing"] for g in gaps)

    def test_no_gap_when_field_answered(self, seeded_db, test_project):
        field = _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1", mandatory=True)
        _add_answer(seeded_db, test_project, field, value=100.0, unit="tCO2e")
        seeded_db.commit()

        gaps = CrossFrameworkTranslator.detect_gaps(seeded_db, test_project.id)
        assert not any(g["field_code"] == SEC_GHG_CODE for g in gaps)

    def test_optional_field_not_gap(self, seeded_db, test_project):
        _add_field(seeded_db, "TEST_SEC_GHG_OPT", "SEC", "Test SEC Scope 3", mandatory=False)
        seeded_db.commit()

        gaps = CrossFrameworkTranslator.detect_gaps(seeded_db, test_project.id)
        assert not any(g["field_code"] == "TEST_SEC_GHG_OPT" for g in gaps)


class TestAlignmentScore:
    def test_score_reflects_coverage(self, seeded_db, test_project):
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1", mandatory=True)
        seeded_db.commit()

        score = CrossFrameworkTranslator.generate_alignment_score(seeded_db, test_project.id)
        assert 0 <= score["alignment_score"] <= 100
        assert "SEC" in score["frameworks"]

    def test_complete_coverage_gives_100(self, seeded_db, test_project):
        # Answer all 3 conftest SFDR fields
        for field in seeded_db.query(RegulationField).filter(RegulationField.framework == "SFDR").all():
            _add_answer(seeded_db, test_project, field, value=10.0, unit="tCO2e")
        seeded_db.commit()

        score = CrossFrameworkTranslator.generate_alignment_score(seeded_db, test_project.id)
        sfdr = score["frameworks"]["SFDR"]
        assert sfdr["total"] == sfdr["covered"]
        assert score["alignment_score"] >= 90  # still low because other frameworks have zero coverage

    def test_supported_frameworks_defined(self):
        assert SUPPORTED_FRAMEWORKS == ["SFDR", "CSRD", "SEC", "UK SDR", "ISSB"]


class TestHarmonization:
    def test_harmonizes_cross_framework_answers(self, seeded_db, test_project):
        # Source: SFDR Scope 1 (approved answer)
        sfdr = _add_field(
            seeded_db, SRC_GHG_CODE, "SFDR", "Test Scope 1 GHG",
            cross_refs=[
                {"framework": "SEC", "field_code": SEC_GHG_CODE, "relationship": "equivalent_disclosure"},
                {"framework": "ISSB", "field_code": ISSB_GHG_CODE, "relationship": "equivalent_disclosure"},
            ],
        )
        _add_answer(seeded_db, test_project, sfdr, value=14000.0, unit="tCO2e")

        # Targets without answers
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1")
        _add_field(seeded_db, ISSB_GHG_CODE, "ISSB", "Test ISSB GHG")
        seeded_db.commit()

        result = CrossFrameworkTranslator.harmonize_disclosures(
            db=seeded_db,
            project_id=test_project.id,
            source_framework="SFDR",
        )

        assert result["success"] is True
        assert result["fields_harmonized"] >= 2
        target_codes = {h["target_field_code"] for h in result["harmonized_fields"]}
        assert SEC_GHG_CODE in target_codes
        assert ISSB_GHG_CODE in target_codes

        # Verify answers were created as Draft with harmonized value
        sec_field = seeded_db.query(RegulationField).filter(
            RegulationField.field_code == SEC_GHG_CODE
        ).first()
        answer = seeded_db.query(FieldAnswer).filter(
            FieldAnswer.project_id == test_project.id,
            FieldAnswer.regulation_field_id == sec_field.id,
            FieldAnswer.is_latest.is_(True),
        ).first()
        assert answer is not None
        assert answer.status == AnswerStatus.DRAFT.value
        assert answer.answer_json["value"] == 14000.0

    def test_harmonize_respects_target_filter(self, seeded_db, test_project):
        sfdr = _add_field(
            seeded_db, SRC_GHG_CODE, "SFDR", "Test Scope 1 GHG",
            cross_refs=[
                {"framework": "SEC", "field_code": SEC_GHG_CODE, "relationship": "equivalent_disclosure"},
                {"framework": "ISSB", "field_code": ISSB_GHG_CODE, "relationship": "equivalent_disclosure"},
            ],
        )
        _add_answer(seeded_db, test_project, sfdr, value=5000.0, unit="tCO2e")
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1")
        _add_field(seeded_db, ISSB_GHG_CODE, "ISSB", "Test ISSB GHG")
        seeded_db.commit()

        result = CrossFrameworkTranslator.harmonize_disclosures(
            db=seeded_db,
            project_id=test_project.id,
            source_framework="SFDR",
            target_frameworks=["SEC"],
        )
        assert result["fields_harmonized"] == 1
        assert result["harmonized_fields"][0]["target_framework"] == "SEC"

    def test_harmonize_skips_already_populated_target(self, seeded_db, test_project):
        sfdr = _add_field(
            seeded_db, SRC_GHG_CODE, "SFDR", "Test Scope 1 GHG",
            cross_refs=[{"framework": "SEC", "field_code": SEC_GHG_CODE, "relationship": "equivalent_disclosure"}],
        )
        _add_answer(seeded_db, test_project, sfdr, value=100.0, unit="tCO2e")

        sec = _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1")
        # target already answered
        _add_answer(seeded_db, test_project, sec, value=99.0, unit="tCO2e")
        seeded_db.commit()

        result = CrossFrameworkTranslator.harmonize_disclosures(
            db=seeded_db,
            project_id=test_project.id,
            source_framework="SFDR",
        )
        assert result["fields_harmonized"] == 0
        assert len(result["skipped_fields"]) >= 1

    def test_harmonize_no_answers_no_op(self, seeded_db, test_project):
        _add_field(seeded_db, SRC_GHG_CODE, "SFDR", "Test Scope 1 GHG",
                   cross_refs=[{"framework": "SEC", "field_code": SEC_GHG_CODE, "relationship": "equivalent_disclosure"}])
        _add_field(seeded_db, SEC_GHG_CODE, "SEC", "Test SEC Scope 1")
        seeded_db.commit()

        result = CrossFrameworkTranslator.harmonize_disclosures(
            db=seeded_db,
            project_id=test_project.id,
            source_framework="SFDR",
        )
        assert result["success"] is True
        assert result["fields_harmonized"] == 0
