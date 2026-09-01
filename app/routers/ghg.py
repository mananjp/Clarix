"""
GHG Calculation Router — GHG Protocol Scope 1/2/3 methodology engine.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.models import User
from app.auth import get_current_user
from app.services.ghg import GHGService

router = APIRouter(prefix="/api/ghg", tags=["ghg"])


class Scope1Request(BaseModel):
    fuel_type: str = Field(..., description="natural_gas|diesel|petrol|coal|fueloil")
    quantity: float = Field(..., description="Quantity of fuel consumed")
    unit: str = Field("litre")


class Scope2Request(BaseModel):
    kwh: float = Field(..., description="Purchased electricity in kWh")
    method: str = Field("location", description="location|market")
    region: str = Field("EU_avg", description="Grid region code")
    market_source: Optional[str] = Field(None, description="Supplier-specific market source")


class Scope3Request(BaseModel):
    category: str = Field(..., description="e.g. purchased_goods, business_travel, investments")
    spend_eur: float = Field(..., description="Spend in EUR")


class PortfolioRequest(BaseModel):
    scope1: float
    scope2: float
    scope3: float
    ev_eur_million: float = Field(..., description="Enterprise value in EUR millions")


@router.post("/scope1")
def calc_scope1(payload: Scope1Request, current_user: User = Depends(get_current_user)):
    return GHGService.calculate_scope1(payload.fuel_type, payload.quantity, payload.unit)


@router.post("/scope2")
def calc_scope2(payload: Scope2Request, current_user: User = Depends(get_current_user)):
    return GHGService.calculate_scope2(payload.kwh, payload.method, payload.region, payload.market_source)


@router.post("/scope3")
def calc_scope3(payload: Scope3Request, current_user: User = Depends(get_current_user)):
    return GHGService.calculate_scope3(payload.category, payload.spend_eur)


@router.post("/portfolio")
def calc_portfolio(payload: PortfolioRequest, current_user: User = Depends(get_current_user)):
    return GHGService.calculate_portfolio(
        payload.scope1, payload.scope2, payload.scope3, payload.ev_eur_million
    )
