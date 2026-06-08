# Gap 3 Implementation Plan — Predictive Transition Analytics (BRSR Trend Engine)

## Overview

Filing a BRSR report is a backward-looking exercise. The next competitive layer — and a significant upsell from pure compliance tooling to strategic ESG advisory — is answering the forward-looking question: "What will our GHG, water, and waste figures look like next year, and what actions would most efficiently reduce them?" This plan adds a Trend Engine and Scenario Planner to the existing workspace, built entirely in Python using data already resident in the PostgreSQL database from previous BRSR cycles.

---

## Problem Statement

### The Gap in Current ESG Tools

Most ESG platforms, including global incumbents, produce:
- Year-over-year comparison tables (manual, static)
- Rating-agency benchmarks (lagged, opaque)
- Generic "best practice" recommendations (not tied to the company's own data)

None of them produce: "Your Scope 2 emissions will exceed your 2025 SBTi target by 23% unless you accelerate renewable energy procurement in Q2." That kind of forward-looking, data-grounded, company-specific insight requires combining historical BRSR data with time-series forecasting and LLM narrative generation — which this plan delivers.

### What BRSR Makes Possible

SEBI BRSR now spans two or more annual filing cycles for most top-1000 companies. That means the workspace already holds at least two data points per BRSR field per company: the prior year and the current year. With even three data points, short-horizon forecasting becomes meaningful. The nine BRSR Core metrics are particularly good candidates because they are quantitative, standardized, and mandated to be consistent across years.

---

## Solution Architecture

### Component 1 — Multi-Year Project Schema Extension

**What it does:** Introduces a `reporting_year` field on `Project`, links historical `FieldAnswer` records across years, and creates a `MetricTimeSeries` view for trend computation.

#### `app/models.py` changes
```python
# Add to Project model
reporting_year = Column(Integer, nullable=True)  # e.g. 2023, 2024, 2025
industry_sector = Column(String(128), nullable=True)  # e.g. "Cement", "IT Services"

# New model: MetricSnapshot (one row per field per project)
class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    regulation_field_id = Column(Integer, ForeignKey("regulation_fields.id"), nullable=False)
    reporting_year = Column(Integer, nullable=False)
    value_numeric = Column(Float, nullable=True)
    value_unit = Column(String(64), nullable=True)
    intensity_denominator = Column(Float, nullable=True)  # Revenue or turnover in INR crore
    intensity_value = Column(Float, nullable=True)
    source_project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    snapshot_created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('company_id', 'regulation_field_id', 'reporting_year'),)
```

#### Database migration
```python
# alembic/versions/xxxx_add_trend_engine.py
def upgrade():
    op.add_column('projects', sa.Column('reporting_year', sa.Integer(), nullable=True))
    op.add_column('projects', sa.Column('industry_sector', sa.String(128), nullable=True))
    op.create_table('metric_snapshots', ...)
```

---

### Component 2 — Snapshot Extraction Pipeline

**What it does:** After a project is finalized (all BRSR Core fields approved), a background job extracts numeric values from `FieldAnswer` records, normalizes units, and writes `MetricSnapshot` rows.

#### `app/services/snapshot_extractor.py`
```python
import re

UNIT_NORMALIZERS = {
    "tco2e": 1.0,
    "tonnes co2e": 1.0,
    "mtco2e": 1_000_000.0,
    "kwh": 1.0,
    "mwh": 1_000.0,
    "gj": 277.778,           # GJ to kWh
    "kl": 1.0,               # Kilolitres for water
    "ml": 0.001,
    "mt": 1.0,               # Metric tonnes for waste
}

def extract_numeric(text: str) -> tuple[float | None, str | None]:
    pattern = r"([\d,]+\.?\d*)\s*([a-zA-Z\/\s%]+)?"
    match = re.search(pattern, text.replace(",", ""))
    if match:
        value = float(match.group(1))
        unit = match.group(2).strip().lower() if match.group(2) else None
        return value, unit
    return None, None

def normalize_to_base_unit(value: float, unit: str) -> float:
    multiplier = UNIT_NORMALIZERS.get(unit, 1.0)
    return value * multiplier

def create_snapshot_from_project(project_id: int, db: Session):
    project = db.query(Project).filter(Project.id == project_id).first()
    answers = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.status == "approved"
    ).all()

    for answer in answers:
        value, unit = extract_numeric(answer.answer_text)
        if value is None:
            continue
        normalized = normalize_to_base_unit(value, unit) if unit else value

        snapshot = MetricSnapshot(
            company_id=project.company_id,
            regulation_field_id=answer.regulation_field_id,
            reporting_year=project.reporting_year,
            value_numeric=normalized,
            value_unit=unit,
            source_project_id=project_id
        )
        db.merge(snapshot)  # upsert on UniqueConstraint
    db.commit()
```

---

### Component 3 — Forecasting Engine

**What it does:** Given ≥2 years of `MetricSnapshot` data for a field, computes next-year point forecast and 80% prediction interval using a linear regression baseline with an optional exponential smoothing layer.

#### `app/services/forecasting.py`
```python
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

def forecast_metric(
    snapshots: list[MetricSnapshot],
    horizon_years: int = 1
) -> dict:
    if len(snapshots) < 2:
        return {"status": "insufficient_data", "min_years_required": 2}

    years = np.array([s.reporting_year for s in snapshots]).reshape(-1, 1)
    values = np.array([s.value_numeric for s in snapshots])

    scaler = StandardScaler()
    years_scaled = scaler.fit_transform(years)

    model = LinearRegression()
    model.fit(years_scaled, values)

    target_year = max(s.reporting_year for s in snapshots) + horizon_years
    target_scaled = scaler.transform([[target_year]])
    forecast_value = model.predict(target_scaled)[0]

    # Residual std for prediction interval
    residuals = values - model.predict(years_scaled)
    residual_std = np.std(residuals)
    z_80 = 1.282  # 80% interval
    lower = forecast_value - z_80 * residual_std
    upper = forecast_value + z_80 * residual_std

    yoy_change_pct = ((values[-1] - values[-2]) / values[-2] * 100) if len(values) >= 2 else None

    return {
        "status": "ok",
        "target_year": target_year,
        "forecast_value": round(forecast_value, 4),
        "lower_bound_80pct": round(lower, 4),
        "upper_bound_80pct": round(upper, 4),
        "trend_direction": "improving" if model.coef_[0] < 0 else "worsening",
        "yoy_change_pct": round(yoy_change_pct, 2) if yoy_change_pct else None,
        "data_points_used": len(snapshots),
        "model": "linear_regression"
    }
```

**Upgrade path:** Once ≥5 years of data are available, swap the backend to `statsmodels.tsa.holtwinters.ExponentialSmoothing` with seasonal decomposition for companies with seasonal energy or water patterns.

---

### Component 4 — Scenario Planner

**What it does:** Accepts a user-defined intervention (e.g., "switch 30% of electricity to renewable by 2026") and recomputes the forecast with the intervention effect applied.

#### `app/services/scenario_planner.py`
```python
from dataclasses import dataclass

@dataclass
class Intervention:
    field_code: str          # e.g. "BRSR_GHG_SCOPE2"
    effect_type: str         # "relative_reduction" | "absolute_reduction"
    effect_magnitude: float  # e.g. 0.30 for 30% reduction
    applicable_from_year: int

def apply_intervention(
    base_forecast: dict,
    intervention: Intervention
) -> dict:
    base_value = base_forecast["forecast_value"]
    if intervention.effect_type == "relative_reduction":
        adjusted = base_value * (1 - intervention.effect_magnitude)
    elif intervention.effect_type == "absolute_reduction":
        adjusted = base_value - intervention.effect_magnitude
    else:
        adjusted = base_value

    delta = base_value - adjusted
    return {
        **base_forecast,
        "scenario_name": f"{int(intervention.effect_magnitude * 100)}% {intervention.effect_type}",
        "scenario_forecast_value": round(adjusted, 4),
        "estimated_reduction": round(delta, 4),
        "intervention_description": f"{intervention.effect_type} of {intervention.effect_magnitude} on {intervention.field_code} from {intervention.applicable_from_year}"
    }
```

---

### Component 5 — LLM Narrative Generator

**What it does:** Takes a `ForecastResult` and generates a 2–3 sentence board-ready narrative insight using Groq or Gemini with a structured prompt, including trend direction, gap to SBTi/regulatory target if provided, and a recommended action.

#### `app/services/narrative_generator.py`
```python
TREND_NARRATIVE_PROMPT = """
You are a sustainability analyst writing board-level ESG insights.

Given the following forecast data for a BRSR metric, write exactly 2-3 sentences:
1. State the trend direction and magnitude using the specific numbers.
2. If a target is provided, state the gap or surplus against the target.
3. Recommend the single most impactful intervention.

Do not use hedging language. Do not use generic advice. Be specific.

Metric: {field_name}
Current value ({current_year}): {current_value} {unit}
Forecast ({forecast_year}): {forecast_value} {unit}
YoY change: {yoy_change_pct}%
Trend: {trend_direction}
Target (if any): {target_value} {unit} by {target_year}
Industry sector: {industry_sector}

Write the insight now:
"""

async def generate_trend_narrative(
    forecast: dict,
    field_name: str,
    current_value: float,
    current_year: int,
    unit: str,
    industry_sector: str,
    target_value: float | None = None,
    target_year: int | None = None,
    llm_client = None
) -> str:
    prompt = TREND_NARRATIVE_PROMPT.format(
        field_name=field_name,
        current_year=current_year,
        current_value=current_value,
        unit=unit,
        forecast_year=forecast["target_year"],
        forecast_value=forecast["forecast_value"],
        yoy_change_pct=forecast.get("yoy_change_pct", "N/A"),
        trend_direction=forecast["trend_direction"],
        target_value=target_value or "Not set",
        target_year=target_year or "N/A",
        industry_sector=industry_sector
    )
    response = await llm_client.chat(prompt)
    return response.strip()
```

---

### Component 6 — API Endpoints

```
POST /api/projects/{project_id}/finalize-snapshots
     → Runs create_snapshot_from_project for the given project
     → Returns count of snapshots created

GET  /api/companies/{company_id}/trends/{field_code}
     → Returns all MetricSnapshot rows + forecast for the field
     → Optional: ?horizon=2 for 2-year forecast
     → Optional: ?target_value=X&target_year=Y for gap-to-target

POST /api/companies/{company_id}/scenarios
     → Body: { field_code, effect_type, effect_magnitude, applicable_from_year }
     → Returns base forecast + scenario forecast side by side

GET  /api/companies/{company_id}/trend-narrative/{field_code}
     → Returns LLM-generated narrative for the metric trend
```

---

### Component 7 — Frontend Trend Dashboard

**New page: `TrendDashboard.jsx`**

Accessible under `/trends` route.

**UI sections:**
1. **Metric Selector Bar** — BRSR Core 9 metrics as pills; click to focus
2. **Trend Chart** — Line chart showing historical values + forecast line + 80% confidence band; rendered with Chart.js or Recharts
3. **Scenario Builder Panel** — Slider inputs for reduction % and target year; live recalculation on change
4. **Insight Card** — LLM-generated narrative below each chart; "Regenerate" button
5. **Gap-to-Target Indicator** — Progress bar showing current trajectory vs. declared SBTi or voluntary target

**Chart component sketch:**
```jsx
<TrendChart
  historical={snapshots}
  forecast={forecastResult}
  scenario={scenarioResult}
  targetLine={{ value: targetValue, year: targetYear }}
  metricName="GHG Scope 2 Emissions"
  unit="tonnes CO₂e"
/>
```

---

## Verification Plan

### Automated Tests
- Seed `MetricSnapshot` with 3 years of synthetic GHG data; verify forecast direction matches known trend
- Test unit normalizer for tCO₂e, MWh, GJ, KL, MT
- Test `apply_intervention` for both `relative_reduction` and `absolute_reduction`
- Verify forecast confidence interval width increases with higher residual variance
- Verify narrative prompt produces non-generic output for a specific sector (e.g., Cement vs. IT Services)

### Manual Verification
1. Finalize two past-cycle projects for the same company
2. Run `/finalize-snapshots` for both
3. Call `/trends/BRSR_GHG_SCOPE1` and verify JSON contains forecast + direction
4. Open Trend Dashboard, verify chart renders historical + forecast line
5. Adjust scenario slider to 20% reduction and verify scenario forecast is 20% below base forecast
6. Click "Generate Insight" and verify narrative references actual numbers and sector

---

## Build Effort Estimate

| Component | Estimated effort |
|---|---|
| `reporting_year` migration + `MetricSnapshot` model | 1 day |
| Snapshot extraction pipeline | 1 day |
| Forecasting engine (linear regression + interval) | 1.5 days |
| Scenario planner | 0.5 days |
| LLM narrative generator + prompt tuning | 1 day |
| API endpoints | 1 day |
| `TrendDashboard.jsx` with Chart.js | 2.5 days |
| Tests and verification | 1 day |
| **Total** | **~10 working days** |

---

## Commercial Positioning

This feature shifts the product from a BRSR filing tool to an ESG performance management system. The difference matters commercially: filing tools compete on price (market is commoditizing toward ₹1–5 lakh/year SaaS) while performance management tools compete on ROI and are sold at ₹10–30 lakh/year or as a managed analytics retainer. The Scenario Planner specifically targets the CFO and Head of Sustainability audience, not just the compliance team, which unlocks a second buying center within the same enterprise customer.
