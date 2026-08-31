import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.database import get_db
from app.models import MetricSnapshot, RegulationField, ReportingProject, User
from app.schemas import ScenarioInterventionRequest
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/organizations/{org_id}/trends/{field_code}", response_model=Dict[str, Any])
async def get_organization_metric_trends(
    org_id: str,
    field_code: str,
    horizon: int = 1,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    snapshots = db.query(MetricSnapshot).join(RegulationField).filter(
        MetricSnapshot.organization_id == org_id,
        RegulationField.field_code == field_code
    ).order_by(MetricSnapshot.reporting_year.asc()).all()

    history = []
    years = []
    values = []
    last_val = 0.0
    last_year = datetime.datetime.utcnow().year
    unit = "units"
    field_name = field_code
    
    for s in snapshots:
        history.append({
            "year": s.reporting_year,
            "value": s.value_numeric,
            "unit": s.value_unit
        })
        years.append(s.reporting_year)
        values.append(s.value_numeric)
        last_val = s.value_numeric
        last_year = s.reporting_year
        if s.value_unit:
            unit = s.value_unit
        if s.regulation_field:
            field_name = s.regulation_field.field_label

    from app.services.forecasting import forecast_metric, generate_trend_narrative
    
    if len(history) >= 2:
        forecast_res = forecast_metric(years, values, horizon_years=horizon)
        project = db.query(ReportingProject).filter(ReportingProject.organization_id == org_id).first()
        sector = project.industry_sector if project else "General"
        
        narrative = await generate_trend_narrative(
            forecast=forecast_res,
            field_name=field_name,
            current_value=last_val,
            current_year=last_year,
            unit=unit,
            industry_sector=sector,
            target_value=target_value,
            target_year=target_year
        )
    else:
        forecast_res = {"status": "insufficient_data", "min_years_required": 2}
        narrative = "Insufficient historical data to calculate trends."

    return {
        "history": history,
        "forecast": forecast_res,
        "narrative": narrative,
        "field_name": field_name,
        "unit": unit
    }


@router.get("/companies/{company_id}/trends/{field_code}", response_model=Dict[str, Any])
async def get_company_metric_trends(
    company_id: str,
    field_code: str,
    horizon: int = 1,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_organization_metric_trends(
        org_id=company_id,
        field_code=field_code,
        horizon=horizon,
        target_value=target_value,
        target_year=target_year,
        db=db,
        current_user=current_user
    )


@router.post("/organizations/{org_id}/scenarios")
def simulate_scenario_intervention(
    org_id: str,
    request: ScenarioInterventionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    snapshots = db.query(MetricSnapshot).join(RegulationField).filter(
        MetricSnapshot.organization_id == org_id,
        RegulationField.field_code == request.field_code
    ).order_by(MetricSnapshot.reporting_year.asc()).all()

    years = [s.reporting_year for s in snapshots]
    values = [s.value_numeric for s in snapshots]

    from app.services.forecasting import forecast_metric, apply_intervention
    if len(years) < 2:
        raise HTTPException(status_code=400, detail="Insufficient historical data (minimum 2 years required).")

    last_year = max(years)
    horizon = request.applicable_from_year - last_year
    if horizon <= 0:
        horizon = 1

    base_forecast = forecast_metric(years, values, horizon_years=horizon)
    scenario_forecast = apply_intervention(
        base_forecast=base_forecast,
        effect_type=request.effect_type,
        effect_magnitude=request.effect_magnitude,
        applicable_from_year=request.applicable_from_year,
        field_code=request.field_code
    )

    return {
        "base_forecast": base_forecast,
        "scenario_forecast": scenario_forecast
    }


@router.post("/companies/{company_id}/scenarios")
def simulate_company_scenario_intervention(
    company_id: str,
    request: ScenarioInterventionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return simulate_scenario_intervention(
        org_id=company_id,
        request=request,
        db=db,
        current_user=current_user
    )


@router.get("/companies/{company_id}/trend-narrative/{field_code}")
async def get_company_trend_narrative(
    company_id: str,
    field_code: str,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await get_organization_metric_trends(
        org_id=company_id,
        field_code=field_code,
        target_value=target_value,
        target_year=target_year,
        db=db,
        current_user=current_user
    )
    return {"narrative": res.get("narrative")}
