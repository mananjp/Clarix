"""
GHG Protocol calculation engine.

Implements Scope 1, 2 and 3 calculation methodologies in line with the GHG
Protocol Corporate Accounting and Reporting Standard, powering SFDR PAI
indicators 1–6 and CSRD's ESRS E1 climate disclosures.

Scope 1 — direct emissions from owned/controlled sources (combustion + process).
Scope 2 — indirect emissions from purchased electricity/steam (location-based
          and market-based methods).
Scope 3 — value chain emissions (supplier-activity or spend-based proxy where
          primary data is unavailable).

All methods return a normalized, auditable result with methodology + emission
factors cited so a disclosure has real provenance rather than a hardcoded value.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in default emission factors (simplified illustrative set)
# Values in kg CO2e per unit; production systems should load these from a
# maintained factor registry (e.g. BEIS/DEFRA, EPA eGRID, IEA).
# ---------------------------------------------------------------------------
# Scope 1: natural gas, diesel, petrol
_S1_FACTORS_KG = {
    "natural_gas": 2.02,      # kg CO2e / m3
    "diesel": 2.68,           # kg CO2e / litre
    "petrol": 2.31,           # kg CO2e / litre
    "coal": 2.46,             # kg CO2e / kg
    "fueloil": 2.98,          # kg CO2e / litre
}

# Scope 2: purchased electricity (location-based grid intensity, kg CO2e / kWh)
_LOCATION_BASED_GRID = {
    "EU_avg": 0.276,          # kg CO2e / kWh (illustrative EU average grid)
    "DE": 0.366,
    "FR": 0.056,
    "UK": 0.240,
}

# Market-based / supplier-specific factor overriding location-based.
_MARKET_BASED_SCOPE2 = {
    "renewable_purchase": 0.010,   # certified green electricity residual mix proxy
}

# Scope 3: spend-based proxy factors (kg CO2e / EUR spend) by upstream category.
_S3_SPEND_FACTORS = {
    "purchased_goods": 0.320,
    "capital_goods": 0.410,
    "transport_upstream": 0.180,
    "business_travel": 0.150,
    "investments": 0.220,          # Category 15 (relevant for asset managers)
}


class GHGFactorRegistry:
    """Reads emission factors, allowing override with a real factor feed later."""

    @staticmethod
    def scope1_factor(source_type: str) -> float:
        return _S1_FACTORS_KG.get(source_type, 2.5)

    @staticmethod
    def scope2_location_factor(region: str) -> float:
        return _LOCATION_BASED_GRID.get(region, _LOCATION_BASED_GRID["EU_avg"])

    @staticmethod
    def scope2_market_factor(source: str) -> float:
        return _MARKET_BASED_SCOPE2.get(source, 0.0)

    @staticmethod
    def scope3_spend_factor(category: str) -> float:
        return _S3_SPEND_FACTORS.get(category, 0.25)


class GHGProtocolCalculator:
    """Stateless GHG Protocol calculation methods (all inputs/outputs explicit)."""

    # ------------------------------------------------------------------
    # Scope 1
    # ------------------------------------------------------------------
    @staticmethod
    def scope1_combustion(*, fuel_type: str, quantity: float, unit: str = "litre") -> Dict[str, Any]:
        """
        Scope 1 emissions from stationary/mobile fuel combustion.
        quantity × emission_factor.
        """
        factor = GHGFactorRegistry.scope1_factor(fuel_type)  # kg CO2e / unit
        tonnes = (quantity * factor) / 1000.0                 # convert kg -> t
        return {
            "scope": 1,
            "methodology": "GHG Protocol: combustion-based (quantity × emission factor)",
            "fuel_type": fuel_type,
            "quantity": quantity,
            "unit": unit,
            "emission_factor_kg_per_unit": factor,
            "emissions_tCO2e": round(tonnes, 3),
            "factor_source": "Clarix embedded factor registry (illustrative)",
        }

    # ------------------------------------------------------------------
    # Scope 2
    # ------------------------------------------------------------------
    @staticmethod
    def scope2_electricity(*, kwh: float, method: str = "location", region: str = "EU_avg", market_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Scope 2 emissions from purchased electricity using the location-based
        or market-based method per the GHG Protocol Scope 2 Guidance.
        """
        if method == "market" and market_source:
            factor = GHGFactorRegistry.scope2_market_factor(market_source)
            method_label = f"market-based ({market_source})"
        else:
            factor = GHGFactorRegistry.scope2_location_factor(region)
            method_label = f"location-based ({region})"

        tonnes = (kwh * factor) / 1000.0
        return {
            "scope": 2,
            "method": method,
            "methodology": f"GHG Protocol Scope 2 Guidance: {method_label}",
            "kwh": kwh,
            "region": region,
            "emission_factor_kg_per_kwh": factor,
            "emissions_tCO2e": round(tonnes, 3),
            "factor_source": "Clarix embedded factor registry (illustrative)",
        }

    # ------------------------------------------------------------------
    # Scope 3
    # ------------------------------------------------------------------
    @staticmethod
    def scope3_spend_based(*, category: str, spend_eur: float) -> Dict[str, Any]:
        """
        Spend-based Scope 3 estimate: spend × spend-based factor. Used where
        primary supplier data is not yet available (proxy estimate).
        """
        factor = GHGFactorRegistry.scope3_spend_factor(category)
        tonnes = (spend_eur * factor) / 1000.0
        return {
            "scope": 3,
            "category": category,
            "methodology": "GHG Protocol: spend-based proxy (Category-specific factor × spend)",
            "spend_eur": spend_eur,
            "spend_factor_kg_per_eur": factor,
            "emissions_tCO2e": round(tonnes, 3),
            "factor_source": "Clarix embedded factor registry (illustrative)",
            "estimate": True,
        }

    # ------------------------------------------------------------------
    # Portfolio / investee aggregation (SFDR PAI context)
    # ------------------------------------------------------------------
    @staticmethod
    def portfolio_total(*, scope1: float, scope2: float, scope3: float) -> Dict[str, Any]:
        """Aggregate across scopes into total financed emissions (tCO2e)."""
        total = scope1 + scope2 + scope3
        return {
            "scope1_tCO2e": round(scope1, 3),
            "scope2_tCO2e": round(scope2, 3),
            "scope3_tCO2e": round(scope3, 3),
            "total_tCO2e": round(total, 3),
            "methodology": "GHG Protocol Corporate Standard aggregation",
        }

    @staticmethod
    def carbon_footprint(*, total_tCO2e: float, ev_eur_million: float) -> Dict[str, Any]:
        """PAI indicator 4: carbon footprint = total emissions / EV (EURm)."""
        footprint = total_tCO2e / ev_eur_million if ev_eur_million else 0.0
        return {
            "value_tCO2e_per_eurm": round(footprint, 3),
            "enterprise_value_eurm": ev_eur_million,
            "methodology": "SFDR RTS Annex I Table 1 Indicator 4 (Scope 1+2+3 over EV)",
        }


class GHGService:
    """Facade exposing GHG calculation methods to routers/tests."""

    @staticmethod
    def calculate_scope1(fuel_type: str, quantity: float, unit: str = "litre") -> Dict[str, Any]:
        return GHGProtocolCalculator.scope1_combustion(fuel_type=fuel_type, quantity=quantity, unit=unit)

    @staticmethod
    def calculate_scope2(kwh: float, method: str = "location", region: str = "EU_avg", market_source: Optional[str] = None) -> Dict[str, Any]:
        return GHGProtocolCalculator.scope2_electricity(
            kwh=kwh, method=method, region=region, market_source=market_source
        )

    @staticmethod
    def calculate_scope3(category: str, spend_eur: float) -> Dict[str, Any]:
        return GHGProtocolCalculator.scope3_spend_based(category=category, spend_eur=spend_eur)

    @staticmethod
    def calculate_portfolio(scope1: float, scope2: float, scope3: float, ev_eur_million: float) -> Dict[str, Any]:
        total = GHGProtocolCalculator.portfolio_total(scope1=scope1, scope2=scope2, scope3=scope3)
        footprint = GHGProtocolCalculator.carbon_footprint(
            total_tCO2e=total["total_tCO2e"], ev_eur_million=ev_eur_million
        )
        return {
            "scopes": total,
            "carbon_footprint": footprint,
            "ghg_protocol_standard": "GHG Protocol Corporate Accounting and Reporting Standard",
        }
