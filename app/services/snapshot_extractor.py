import re
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models import ReportingProject, FieldAnswer, MetricSnapshot

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
    if not text:
        return None, None
    
    # Remove commas
    clean_text = text.replace(",", "")
    
    # Look for a number (int or float) optionally followed by unit words
    pattern = r"([\d\.]+)\s*([a-zA-Z0-9\/\s%]+)?"
    match = re.search(pattern, clean_text)
    if match:
        try:
            value = float(match.group(1))
            unit = match.group(2).strip().lower() if match.group(2) else None
            if unit:
                # Remove extra trailing spaces or punctuation
                unit = re.sub(r'[^a-z0-9\s%]', '', unit).strip()
            return value, unit
        except ValueError:
            return None, None
    return None, None

def normalize_to_base_unit(value: float, unit: str) -> float:
    if not unit:
        return value
        
    # Check simple direct match
    if unit in UNIT_NORMALIZERS:
        return value * UNIT_NORMALIZERS[unit]
    
    # Try substring matches
    for key, multiplier in UNIT_NORMALIZERS.items():
        if key in unit:
            return value * multiplier
            
    return value

def create_snapshot_from_project(project_id: str, db: Session) -> int:
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        return 0

    answers = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.status == "Approved",
        FieldAnswer.is_latest == True
    ).all()

    year = project.reporting_year
    if not year:
        # Try to parse year from project name, e.g. "2025"
        year_match = re.search(r"\b(20\d{2})\b", project.name)
        if year_match:
            year = int(year_match.group(1))
        else:
            year = datetime.datetime.utcnow().year

    count = 0
    for answer in answers:
        if not answer.answer_text:
            continue
            
        value, unit = extract_numeric(answer.answer_text)
        if value is None:
            continue
            
        normalized = normalize_to_base_unit(value, unit) if unit else value

        # Try to see if snapshot already exists
        snapshot = db.query(MetricSnapshot).filter(
            MetricSnapshot.organization_id == project.organization_id,
            MetricSnapshot.regulation_field_id == answer.regulation_field_id,
            MetricSnapshot.reporting_year == year
        ).first()

        if snapshot:
            snapshot.value_numeric = normalized
            snapshot.value_unit = unit
            snapshot.source_project_id = project_id
            snapshot.snapshot_created_at = datetime.datetime.utcnow()
        else:
            snapshot = MetricSnapshot(
                id=str(uuid.uuid4()),
                organization_id=project.organization_id,
                regulation_field_id=answer.regulation_field_id,
                reporting_year=year,
                value_numeric=normalized,
                value_unit=unit,
                source_project_id=project_id,
                snapshot_created_at=datetime.datetime.utcnow()
            )
            db.add(snapshot)
        count += 1
        
    db.commit()
    return count
