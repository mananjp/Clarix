"""
Third-party ESG data feed integration.

Provides a pluggable provider abstraction so Clarix can ingest investee-company
ESG metrics from external data vendors (Sustainalytics, MSCI) instead of relying
solely on user-uploaded PDFs. This directly addresses the SFDR PAI "data
availability" gap for asset managers.

Config via env vars:
    ESG_FEED_PROVIDER   = sustainalytics | msci | mock (default: mock)
    SUSTAINALYTICS_API_KEY
    SUSTAINALYTICS_BASE_URL
    MSCI_ESG_API_KEY
    MSCI_ESG_BASE_URL

The `mock` provider returns realistic synthetic data so the pipeline is
exercisable without vendor credentials, and makes provider implementations
testable in CI.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import RegulationField

logger = logging.getLogger(__name__)


class ESGFetchError(Exception):
    """Raised when fetching from a third-party ESG data provider fails."""


class ESGDataProvider(ABC):
    """Abstract interface for an ESG data feed provider."""

    @abstractmethod
    def fetch_company_metrics(self, isin: str, fields: List[str]) -> Dict[str, Any]:
        """
        Fetch ESG metrics for a single investee company identified by ISIN.
        Returns a dict mapping requested field codes to extracted values.
        """


class SustainalyticsProvider(ESGDataProvider):
    """
    Sustainalytics ESG Risk Ratings API integration.

    Sustainalytics exposes investee ESG Risk Ratings and metric data. The
    exact auth/endpoint varies by licensing agreement; this provider uses the
    documented API-key header pattern and a configurable base URL so it can be
    pointed at any compatible gateway.
    """

    def __init__(self):
        self.api_key = os.getenv("SUSTAINALYTICS_API_KEY", "")
        self.base_url = os.getenv("SUSTAINALYTICS_BASE_URL", "https://api.sustainalytics.com")
        if not self.api_key:
            raise ESGFetchError(
                "SUSTAINALYTICS_API_KEY not set. Configure the provider before use."
            )

    def _get_json(self, path: str) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ESGFetchError(f"Sustainalytics API error {e.code}: {e.reason}")
        except Exception as e:
            raise ESGFetchError(f"Sustainalytics request failed: {e}")

    def fetch_company_metrics(self, isin: str, fields: List[str]) -> Dict[str, Any]:
        payload = self._get_json(f"/v2/companies/{isin}/esg-ratings")
        # Map vendor payload keys to Clarix field codes. A real integration
        # would map the vendor schema to the canonical field code space.
        result = {}
        for f in fields:
            vendor_key = {
                "PAI_GHG_SCOPE1": "scope1",
                "PAI_GHG_SCOPE2": "scope2",
                "PAI_GHG_SCOPE3": "scope3",
                "PAI_FOSSIL_FUEL": "fossilFuelExposure",
                "PAI_CARBON_FOOTPRINT": "carbonFootprint",
            }.get(f)
            if vendor_key and vendor_key in payload:
                result[f] = payload[vendor_key]
        return result


class MSCIProvider(ESGDataProvider):
    """MSCI ESG Research API integration (configurable base URL / auth header)."""

    def __init__(self):
        self.api_key = os.getenv("MSCI_ESG_API_KEY", "")
        self.base_url = os.getenv("MSCI_ESG_BASE_URL", "https://esg.msci.com/api/v1")
        if not self.api_key:
            raise ESGFetchError("MSCI_ESG_API_KEY not set. Configure the provider before use.")

    def _get_json(self, path: str) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ESGFetchError(f"MSCI API error {e.code}: {e.reason}")
        except Exception as e:
            raise ESGFetchError(f"MSCI request failed: {e}")

    def fetch_company_metrics(self, isin: str, fields: List[str]) -> Dict[str, Any]:
        payload = self._get_json(f"/issuer/{isin}/esg")
        result = {}
        for f in fields:
            vendor_key = {
                "PAI_GHG_SCOPE1": "ghg_scope1",
                "PAI_GHG_SCOPE2": "ghg_scope2",
                "PAI_GHG_SCOPE3": "ghg_scope3",
            }.get(f)
            if vendor_key and vendor_key in payload:
                result[f] = payload[vendor_key]
        return result


class MockESGProvider(ESGDataProvider):
    """
    Deterministic synthetic provider for development, tests, and demos.
    Returns plausible investee metrics regardless of credentials.
    """

    _MOCK_BY_FIELD = {
        "PAI_GHG_SCOPE1": {"value": 14820.0, "unit": "tCO2e"},
        "PAI_GHG_SCOPE2": {"value": 8450.0, "unit": "tCO2e"},
        "PAI_GHG_SCOPE3": {"value": 112400.0, "unit": "tCO2e"},
        "PAI_CARBON_FOOTPRINT": {"value": 84.6, "unit": "tCO2e/EURm"},
        "PAI_FOSSIL_FUEL": {"value": 2.4, "unit": "%"},
        "PAI_BOARD_GENDER_DIVERSITY": {"value": 34.2, "unit": "%"},
    }

    def fetch_company_metrics(self, isin: str, fields: List[str]) -> Dict[str, Any]:
        return {
            f: dict(self._MOCK_BY_FIELD[f]) for f in fields if f in self._MOCK_BY_FIELD
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_esg_provider() -> ESGDataProvider:
    provider = os.getenv("ESG_FEED_PROVIDER", "mock").strip().lower()
    if provider == "sustainalytics":
        return SustainalyticsProvider()
    if provider == "msci":
        return MSCIProvider()
    return MockESGProvider()


class ESGDataFeedService:
    """
    High-level service that fetches investee ESG metrics from the configured
    provider and records them in a form the intake pipeline can consume.
    """

    @staticmethod
    def resolve_field_codes(db: Session, framework: str = "SFDR") -> List[str]:
        """Return the canonical numeric field codes to request for a framework."""
        rows = db.query(RegulationField).filter(
            RegulationField.framework == framework,
            RegulationField.field_kind == "numeric",
        ).all()
        return [r.field_code for r in rows]

    @staticmethod
    def fetch_for_company(
        db: Session,
        *,
        isin: str,
        framework: str = "SFDR",
        requested_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch investee ESG metrics for a company identified by ISIN.
        Returns a normalized payload ready to merge into intake/submission flows.
        """
        provider_cls = get_esg_provider()
        fields = requested_fields or ESGDataFeedService.resolve_field_codes(db, framework)
        try:
            metrics = provider_cls.fetch_company_metrics(isin, fields)
            logger.info("Fetched %d metrics from provider for ISIN %s", len(metrics), isin)
            return {
                "success": True,
                "provider": os.getenv("ESG_FEED_PROVIDER", "mock"),
                "isin": isin,
                "framework": framework,
                "metrics": metrics,
                "coverage": round(len(metrics) / len(fields) * 100, 1) if fields else 0.0,
            }
        except ESGFetchError as e:
            logger.warning("ESG data feed fetch failed for ISIN %s: %s", isin, e)
            return {"success": False, "isin": isin, "error": str(e), "metrics": {}}
