"""
Contract tests for GenerationService: ensures both Groq and fallback paths
return schema-valid output.
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.services.generation import GenerationService


REQUIRED_EVIDENCE_KEYS = {"field_code", "status", "evidence_quote", "extracted_value", "confidence", "reasoning_short"}
REQUIRED_ANSWER_KEYS = {"answer_text", "answer_json", "model_name"}


class TestGenerationServiceContract:
    """Verify both Groq and simulator paths produce schema-valid output."""

    SAMPLE_CHUNKS = [
        {
            "id": "chunk_1",
            "page_no": 1,
            "section_title": "GHG Emissions",
            "chunk_text": "The fund's Scope 1 greenhouse gas emissions totalled 14,820 tCO2e for the reporting period.",
            "document_id": "doc_1",
        },
        {
            "id": "chunk_2",
            "page_no": 5,
            "section_title": "Fossil Fuel Exposure",
            "chunk_text": "Portfolio exposure to fossil fuel companies was limited to 2.4% of net assets.",
            "document_id": "doc_1",
        },
    ]

    def test_simulate_evidence_extraction_schema(self):
        """Simulator fallback should return all required keys."""
        result = GenerationService.simulate_evidence_extraction(
            field_code="PAI_GHG_SCOPE1",
            field_label="Scope 1 GHG emissions",
            field_kind="numeric",
            chunks=self.SAMPLE_CHUNKS,
        )
        assert isinstance(result, dict)
        for key in REQUIRED_EVIDENCE_KEYS:
            assert key in result, f"Missing key: {key}"
        assert result["status"] in ("found", "missing", "uncertain")
        assert isinstance(result["confidence"], (int, float))
        assert 0.0 <= result["confidence"] <= 1.0

    def test_simulate_answer_drafting_schema(self):
        """Simulator fallback for drafting should return all required keys."""
        evidence = {
            "field_code": "PAI_GHG_SCOPE1",
            "status": "found",
            "evidence_quote": "Scope 1 emissions were 14,820 tCO2e.",
            "extracted_value": {"value": 14820.0, "unit": "tCO2e"},
            "confidence": 0.95,
            "reasoning_short": "Test",
        }
        result = GenerationService.simulate_answer_drafting(
            field_code="PAI_GHG_SCOPE1",
            field_label="Scope 1 GHG emissions",
            field_kind="numeric",
            evidence=evidence,
        )
        assert isinstance(result, dict)
        for key in REQUIRED_ANSWER_KEYS:
            assert key in result, f"Missing key: {key}"
        assert isinstance(result["answer_text"], str)
        assert len(result["answer_text"]) > 10

    def test_extract_evidence_falls_back_without_groq(self):
        """Without GROQ_API_KEY, extract_evidence should fall back to simulator."""
        # Temporarily clear the key
        original = os.environ.get("GROQ_API_KEY", "")
        os.environ["GROQ_API_KEY"] = ""
        try:
            result = GenerationService.extract_evidence(
                field_code="PAI_GHG_SCOPE1",
                field_label="Scope 1 GHG emissions",
                field_kind="numeric",
                chunks=self.SAMPLE_CHUNKS,
            )
            assert isinstance(result, dict)
            assert result["status"] in ("found", "missing", "uncertain")
        finally:
            os.environ["GROQ_API_KEY"] = original

    def test_draft_answer_with_missing_evidence(self):
        """Drafting with missing evidence should return a valid response."""
        evidence = {
            "field_code": "PAI_GHG_SCOPE1",
            "status": "missing",
            "evidence_quote": None,
            "extracted_value": None,
            "confidence": 0.0,
            "reasoning_short": "No evidence found",
        }
        result = GenerationService.draft_answer(
            field_code="PAI_GHG_SCOPE1",
            field_label="Scope 1 GHG emissions",
            field_kind="numeric",
            evidence=evidence,
        )
        assert isinstance(result, dict)
        assert "answer_text" in result
        assert "model_name" in result

    def test_fossil_fuel_extraction(self):
        """Test fossil fuel field simulation returns correct schema."""
        result = GenerationService.simulate_evidence_extraction(
            field_code="PAI_FOSSIL_FUEL",
            field_label="Fossil fuel sector exposure",
            field_kind="numeric",
            chunks=self.SAMPLE_CHUNKS,
        )
        assert result["status"] == "found"
        assert result["confidence"] > 0.5

    def test_missing_field_extraction(self):
        """An unknown field with no matching content should return missing."""
        result = GenerationService.simulate_evidence_extraction(
            field_code="UNKNOWN_FIELD_XYZ",
            field_label="Unknown metric",
            field_kind="numeric",
            chunks=[{"id": "c1", "page_no": 1, "chunk_text": "Lorem ipsum dolor sit amet.", "document_id": "d1"}],
        )
        assert result["status"] == "missing"
        assert result["confidence"] == 0.0
