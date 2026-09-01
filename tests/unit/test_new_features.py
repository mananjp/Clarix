"""
Unit tests for the Phase 1-4 additions: Auditor, XBRL, ESG feed, regulatory
content, double materiality, GHG, and benchmarking services.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")
os.environ["ESG_FEED_PROVIDER"] = "mock"

from app.models import (
    DoubleMaterialityAssessment, ESRS_TOPICS,
)
from app.services.auditor import AuditorService
from app.services.xbrl import XBRLExportService
from app.services.esg_data_feed import ESGDataFeedService, MockESGProvider
from app.services.regulatory_content import RegulatoryContentService
from app.services.double_materiality import DoubleMaterialityService
from app.services.ghg import GHGService
from app.services.benchmarking import BenchmarkingService
from app.services.export import ExportService


class TestAuditorService:
    def test_assurance_pack_build(self, seeded_db, test_project):
        pack = AuditorService.build_assurance_pack(seeded_db, test_project.id)
        assert pack["project_id"] == test_project.id
        assert "coverage" in pack
        assert "documents" in pack

    def test_assurance_zip_bytes(self, seeded_db, test_project):
        data = AuditorService.build_assurance_zip_bytes(seeded_db, test_project.id)
        import zipfile
        import io
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        assert "assurance_manifest.json" in names
        assert "evidence_mapping.csv" in names


class TestXBRL:
    def test_xbrl_instance(self, seeded_db, test_project):
        xbrl = XBRLExportService.generate_xbrl_instance(seeded_db, test_project.id)
        assert "<xbrl" in xbrl
        assert "context" in xbrl.lower()

    def test_inline_xbrl(self, seeded_db, test_project):
        ix = XBRLExportService.generate_inline_xbrl_export(seeded_db, test_project.id)
        assert "<html" in ix.lower()
        assert "ix:nonFraction" in ix

    def test_generate_all(self, seeded_db, test_project):
        result = XBRLExportService.generate_all(seeded_db, test_project.id)
        assert "xbrl" in result and "inline_xbrl" in result

    def test_esrs_taxonomy_namespace_and_mapped_concepts(self):
        """No placeholder taxonomy: use the real EFRAG ESRS Set 1 namespace, and
        every configured SFDR field must map to a real (known) ESRS concept."""
        assert XBRLExportService.EXAMPLE_TAXONOMY_NS == \
            "https://xbrl.efrag.org/taxonomy/esrs/2023-12-22"
        verified = {
            "PAI_GHG_SCOPE1": "GrossScope1GreenhouseGasEmissions",
            "PAI_GHG_SCOPE2": "GrossMarketBasedScope2GreenhouseGasEmissions",
            "PAI_GHG_SCOPE3": "GrossScope3GreenhouseGasEmissions",
            "PAI_GHG_TOTAL": "GrossGreenhouseGasEmissions",
            "PAI_FOSSIL_FUEL": "RevenueFromFossilFuelCoalOilAndGasSector",
        }
        for code, expected in verified.items():
            assert XBRLExportService._taxonomy_name(code) == expected, code


class TestESGDataFeed:
    def test_mock_provider(self):
        provider = MockESGProvider()
        metrics = provider.fetch_company_metrics("US1234567890", ["PAI_GHG_SCOPE1", "PAI_FOSSIL_FUEL"])
        assert metrics["PAI_GHG_SCOPE1"]["value"] == 14820.0
        assert metrics["PAI_FOSSIL_FUEL"]["value"] == 2.4

    def test_fetch_for_company_mock(self, seeded_db):
        result = ESGDataFeedService.fetch_for_company(
            seeded_db, isin="US1234567890", framework="SFDR"
        )
        assert result["success"] is True
        assert result["metrics"]


class TestRegulatoryContent:
    def test_stale_fields(self, seeded_db):
        stale = RegulatoryContentService.stale_fields(seeded_db)
        assert isinstance(stale, list)

    def test_list_instruments(self):
        instruments = RegulatoryContentService.list_instruments()
        assert len(instruments) >= 1
        assert instruments[0]["instrument"] == "SFDR"


class TestDoubleMateriality:
    def test_initialize_topics(self, seeded_db):
        rows = DoubleMaterialityService.initialize_topics(
            seeded_db, org_id="test_org", project_id=None, actor_id="test_user"
        )
        assert len(rows) == len(ESRS_TOPICS)

    def test_score_and_verdict(self, seeded_db):
        DoubleMaterialityService.initialize_topics(
            seeded_db, org_id="test_org", project_id=None, actor_id="test_user"
        )
        row = seeded_db.query(DoubleMaterialityAssessment).filter(
            DoubleMaterialityAssessment.esrs_topic == "E1"
        ).first()
        scored = DoubleMaterialityService.score_topic(
            seeded_db, assessment_id=row.id,
            financial_materiality=80.0, impact_materiality=70.0,
            actor_id="test_user",
        )
        assert scored.combined_verdict == "Material"

    def test_verdict_not_material(self):
        from app.services.double_materiality import DoubleMaterialityService as S
        assert S._verdict(10.0, 20.0, 50.0) == "NotMaterial"


class TestGHG:
    def test_scope1(self):
        r = GHGService.calculate_scope1("diesel", 1000.0, "litre")
        assert r["scope"] == 1
        assert r["emissions_tCO2e"] > 0

    def test_scope2_location(self):
        r = GHGService.calculate_scope2(100000.0, "location", "EU_avg")
        assert r["scope"] == 2
        assert r["emissions_tCO2e"] > 0

    def test_scope3(self):
        r = GHGService.calculate_scope3("purchased_goods", 50000.0)
        assert r["scope"] == 3
        assert r["estimate"] is True

    def test_portfolio(self):
        r = GHGService.calculate_portfolio(10, 20, 30, 100)
        assert r["scopes"]["total_tCO2e"] == 60
        assert "carbon_footprint" in r


class TestBenchmarking:
    def test_benchmark_metric_no_data(self, seeded_db):
        result = BenchmarkingService.benchmark_metric(
            seeded_db, regulation_field_id="nonexistent", reporting_year=2025
        )
        assert result["status"] == "insufficient_peer_data"


class TestExportFrameworkParam:
    def test_markdown_framework_param(self, seeded_db, test_project):
        report = ExportService.generate_markdown_report(seeded_db, test_project.id, "SFDR")
        assert "SFDR Disclosure Package" in report
