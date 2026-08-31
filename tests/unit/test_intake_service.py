"""
Unit tests for Investee & Supply Chain Data Intake Portal (Phase 4).
"""

import os
import sys

import pytest
from app.models import FieldAnswer
from app.services.intake import DataIntakeService

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestDataIntakeService:
    def test_create_intake_request(self, db_session, test_project):
        req = DataIntakeService.create_request(
            db_session,
            project_id=test_project.id,
            organization_id=test_project.organization_id,
            target_company_name="Nordic Solar A/S",
            target_company_email="esg@nordicsolar.dk",
            requested_framework="SFDR",
            requested_field_codes=["PAI_GHG_SCOPE1", "PAI_FOSSIL_FUEL"],
            expiry_days=14,
        )
        assert req.id.startswith("intake_")
        assert len(req.token) >= 32
        assert req.target_company_name == "Nordic Solar A/S"
        assert req.status == "Pending"

    def test_get_public_request_details(self, db_session, test_project):
        req = DataIntakeService.create_request(
            db_session,
            project_id=test_project.id,
            organization_id=test_project.organization_id,
            target_company_name="Green Energy Ltd",
            requested_field_codes=["PAI_GHG_SCOPE1"],
        )
        details = DataIntakeService.get_public_request_details(db_session, req.token)
        assert details["target_company_name"] == "Green Energy Ltd"
        assert details["status"] == "Pending"
        assert len(details["requested_fields"]) >= 1

    def test_get_invalid_token_raises(self, db_session):
        with pytest.raises(ValueError, match="Invalid or unrecognized intake token"):
            DataIntakeService.get_public_request_details(db_session, "nonexistent_token_123")

    def test_process_investee_submission(self, db_session, test_project):
        req = DataIntakeService.create_request(
            db_session,
            project_id=test_project.id,
            organization_id=test_project.organization_id,
            target_company_name="EcoSupply Co",
            requested_field_codes=["PAI_GHG_SCOPE1"],
        )
        sub = DataIntakeService.process_investee_submission(
            db_session,
            token=req.token,
            company_name="EcoSupply Co",
            contact_name="Lars Hansen",
            contact_email="lars@ecosupply.com",
            submitted_values={"PAI_GHG_SCOPE1": {"value": 850.0, "unit": "tCO2e"}},
            file_bytes=b"Scope 1 emissions: 850 tCO2e for fiscal year 2025.",
            file_name="ecosupply_audit_2025.txt",
        )
        assert sub.id.startswith("sub_")
        assert sub.company_name == "EcoSupply Co"
        assert sub.file_hash is not None
        assert req.status == "Submitted"

    def test_merge_submission_into_project(self, db_session, test_project, seeded_db):
        req = DataIntakeService.create_request(
            db_session,
            project_id=test_project.id,
            organization_id=test_project.organization_id,
            target_company_name="CleanTech BV",
            requested_field_codes=["PAI_GHG_SCOPE1"],
        )
        sub = DataIntakeService.process_investee_submission(
            db_session,
            token=req.token,
            company_name="CleanTech BV",
            submitted_values={"PAI_GHG_SCOPE1": {"value": 450.0, "unit": "tCO2e"}},
        )

        res = DataIntakeService.merge_submission(
            db_session,
            submission_id=sub.id,
            reviewer_id="test_user",
        )
        assert "PAI_GHG_SCOPE1" in res["merged_fields"]
        assert sub.status == "Merged"

        # Verify FieldAnswer in project was updated
        answer = db_session.query(FieldAnswer).filter(
            FieldAnswer.project_id == test_project.id,
            FieldAnswer.is_latest.is_(True),
        ).first()
        assert answer is not None
        assert "CleanTech BV" in answer.answer_text
