import math
from typing import List, Dict, Any, Optional

def linear_regression(x: List[float], y: List[float]) -> tuple[float, float]:
    n = len(x)
    if n == 0:
        return 0.0, 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))
    
    if den == 0:
        slope = 0.0
        intercept = mean_y
    else:
        slope = num / den
        intercept = mean_y - slope * mean_x
        
    return slope, intercept

def calculate_residuals_std(x: List[float], y: List[float], slope: float, intercept: float) -> float:
    n = len(x)
    if n <= 1:
        return 0.0
    residuals_sq = []
    for i in range(n):
        pred = slope * x[i] + intercept
        residuals_sq.append((y[i] - pred) ** 2)
    
    variance = sum(residuals_sq) / n
    return math.sqrt(variance)

def forecast_metric(
    years: List[int],
    values: List[float],
    horizon_years: int = 1
) -> Dict[str, Any]:
    n = len(years)
    if n < 2:
        return {"status": "insufficient_data", "min_years_required": 2}

    # Sort data by year
    sorted_pairs = sorted(zip(years, values))
    x = [float(p[0]) for p in sorted_pairs]
    y = [float(p[1]) for p in sorted_pairs]

    slope, intercept = linear_regression(x, y)
    
    last_year = x[-1]
    target_year = int(last_year + horizon_years)
    forecast_value = slope * target_year + intercept

    # Residual std for prediction interval
    residual_std = calculate_residuals_std(x, y, slope, intercept)
    
    # 80% prediction interval z-score = 1.282
    z_80 = 1.282
    lower = forecast_value - z_80 * residual_std
    upper = forecast_value + z_80 * residual_std

    yoy_change_pct = None
    if len(y) >= 2:
        prev_val = y[-2]
        if prev_val != 0:
            yoy_change_pct = ((y[-1] - prev_val) / prev_val) * 100

    return {
        "status": "ok",
        "target_year": target_year,
        "forecast_value": round(forecast_value, 4),
        "lower_bound_80pct": round(max(0.0, lower), 4),
        "upper_bound_80pct": round(upper, 4),
        "trend_direction": "improving" if slope < 0 else "worsening",
        "yoy_change_pct": round(yoy_change_pct, 2) if yoy_change_pct is not None else None,
        "data_points_used": n,
        "model": "linear_regression"
    }

def apply_intervention(
    base_forecast: dict,
    effect_type: str,
    effect_magnitude: float,
    applicable_from_year: int,
    field_code: str
) -> dict:
    if base_forecast.get("status") != "ok":
        return base_forecast

    base_value = base_forecast["forecast_value"]
    if effect_type == "relative_reduction":
        adjusted = base_value * (1 - effect_magnitude)
    elif effect_type == "absolute_reduction":
        adjusted = base_value - effect_magnitude
    else:
        adjusted = base_value

    adjusted = max(0.0, adjusted)
    delta = base_value - adjusted
    return {
        **base_forecast,
        "scenario_name": f"{int(effect_magnitude * 100)}% {effect_type.replace('_', ' ')}" if effect_type == "relative_reduction" else f"{effect_magnitude} absolute reduction",
        "scenario_forecast_value": round(adjusted, 4),
        "estimated_reduction": round(delta, 4),
        "intervention_description": f"{effect_type.replace('_', ' ').capitalize()} of {effect_magnitude} on {field_code} starting {applicable_from_year}"
    }

async def generate_trend_narrative(
    forecast: dict,
    field_name: str,
    current_value: float,
    current_year: int,
    unit: str,
    industry_sector: str,
    target_value: float | None = None,
    target_year: int | None = None,
) -> str:
    if forecast.get("status") != "ok":
        return "Insufficient historical data to generate predictive sustainability analytics."

    from app.services.generation import GenerationService
    from app.config import DEFAULT_MODEL

    client = GenerationService.get_groq_client()
    
    prompt = (
        "You are a sustainability analyst writing board-level ESG insights.\n\n"
        f"Given the following forecast data for a BRSR metric, write exactly 2-3 sentences:\n"
        f"1. State the trend direction and magnitude using the specific numbers.\n"
        f"2. If a target is provided (e.g. {target_value} {unit} by {target_year}), state the gap or surplus against the target.\n"
        f"3. Recommend the single most impactful intervention for the {industry_sector or 'General'} sector.\n\n"
        "Do not use hedging language. Do not use generic advice. Be specific.\n\n"
        f"Metric: {field_name}\n"
        f"Current value ({current_year}): {current_value} {unit}\n"
        f"Forecast ({forecast.get('target_year')}): {forecast.get('forecast_value')} {unit}\n"
        f"YoY change: {forecast.get('yoy_change_pct') or 'N/A'}%\n"
        f"Trend: {forecast.get('trend_direction')}\n"
        f"Target (if any): {target_value or 'Not set'} {unit} by {target_year or 'N/A'}\n"
        f"Industry sector: {industry_sector or 'General'}\n\n"
        "Write the insight now:"
    )

    if client:
        try:
            # Run in executor to prevent blocking event loop since groq client might be synchronous
            import asyncio
            loop = asyncio.get_event_loop()
            def call_groq():
                response = client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a professional sustainability analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            
            return await loop.run_in_executor(None, call_groq)
        except Exception as e:
            print(f"Error generating narrative with Groq: {e}. Falling back to simulation.")

    # High-fidelity simulation fallback
    trend_desc = forecast.get("trend_direction", "stable")
    change_direction = "decrease" if trend_desc == "improving" else "increase"
    
    sentence1 = f"The historical trend for {field_name} indicates an {trend_desc} trajectory, with a projected value of {forecast.get('forecast_value')} {unit} in {forecast.get('target_year')}, representing a steady year-on-year {change_direction}."
    
    if target_value is not None and target_year is not None:
        gap = forecast.get('forecast_value') - target_value
        if gap > 0:
            sentence2 = f"Based on this baseline projection, the organization will miss the stated target of {target_value} {unit} by {round(gap, 2)} {unit}."
        else:
            sentence2 = f"Based on this baseline projection, the organization is on track to successfully meet the target of {target_value} {unit} by {round(abs(gap), 2)} {unit}."
    else:
        sentence2 = "No formal carbon or sustainability target has been configured for comparison."
        
    sector_lower = (industry_sector or "").lower()
    if "cement" in sector_lower:
        sentence3 = "To accelerate progress, the organization should focus on clinker substitution rates and waste heat recovery systems."
    elif "it" in sector_lower or "services" in sector_lower or "software" in sector_lower:
        sentence3 = "To accelerate progress, sourcing renewable electricity power purchase agreements (PPAs) for data center operations remains the most critical lever."
    else:
        sentence3 = "Implementing energy efficiency audits and expanding onsite solar generation capacity is recommended to achieve the desired reductions."
        
    return f"{sentence1} {sentence2} {sentence3}"
