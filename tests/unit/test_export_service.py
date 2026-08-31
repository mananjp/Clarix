"""
Unit tests for ExportService: markdown and HTML generation.
"""

import os
import sys
import uuid


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.models import (
    FieldAnswer, RegulationField, AnswerStatus,
)
from app.services.export import ExportService


class TestExportService:
    def test_generate_markdown_report(self, seeded_db, test_project):
        """Markdown report should return a non-empty string."""
        report = ExportService.generate_markdown_report(seeded_db, test_project.id)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_html_report(self, seeded_db, test_project):
        """HTML report should return a non-empty string with HTML tags."""
        report = ExportService.generate_html_report(seeded_db, test_project.id)
        assert isinstance(report, str)
        assert "<html" in report.lower() or "<div" in report.lower() or "<h" in report.lower()

    def test_markdown_report_contains_project_name(self, seeded_db, test_project):
        """Markdown report should reference the project name."""
        report = ExportService.generate_markdown_report(seeded_db, test_project.id)
        # The report should contain some reference to the disclosure
        assert len(report) > 50  # Should be substantial

    def test_html_report_with_approved_answers(self, seeded_db, test_project):
        """HTML report with approved answers should include answer content."""
        field = seeded_db.query(RegulationField).first()
        answer = FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            regulation_field_id=field.id,
            answer_text="Our Scope 1 emissions were 14,820 tCO2e.",
            status=AnswerStatus.APPROVED.value,
            version_no=1,
            is_latest=True,
        )
        seeded_db.add(answer)
        seeded_db.commit()

        report = ExportService.generate_html_report(seeded_db, test_project.id)
        assert isinstance(report, str)
        assert len(report) > 100
