import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import ReportingProject, WhatIfScenario, AuditLog, User
from app.schemas import (
    WhatIfScenarioCreate, WhatIfScenarioResponse,
    ScenarioParseRequest, ScenarioParseResponse
)
from app.auth import get_current_user
from app.services.what_if_engine import WhatIfEngine

router = APIRouter(prefix="/api", tags=["what-if"])


@router.get("/what-if/templates")
def get_what_if_templates():
    """Return pre-built what-if scenario templates."""
    return WhatIfEngine.get_templates()


@router.post("/projects/{project_id}/what-if/parse", response_model=ScenarioParseResponse)
def parse_what_if_scenario(project_id: str, parse_in: ScenarioParseRequest,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Parse a natural language or hybrid context scenario input."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    result = WhatIfEngine.parse_scenario(
        db=db,
        project_id=project_id,
        params=parse_in.model_dump()
    )
    return result


@router.post("/projects/{project_id}/what-if", response_model=WhatIfScenarioResponse)
def run_what_if_scenario(project_id: str, scenario_in: WhatIfScenarioCreate,
                         db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    """Run a what-if legal risk simulation on a project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    result = WhatIfEngine.run_scenario(
        db=db,
        project_id=project_id,
        scenario_name=scenario_in.scenario_name,
        scenario_description=scenario_in.scenario_description,
        parameters=scenario_in.parameters
    )

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="what_if",
        entity_id=result.id,
        action="simulate",
        actor_id="system",
        project_id=project_id,
        payload={"scenario": scenario_in.scenario_name, "risk_score": result.risk_score}
    )
    db.add(audit)
    db.commit()

    return result


@router.get("/projects/{project_id}/what-if", response_model=List[WhatIfScenarioResponse])
def get_project_what_if_scenarios(project_id: str, db: Session = Depends(get_db),
                                  current_user: User = Depends(get_current_user)):
    """List all what-if scenarios run for a project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    return db.query(WhatIfScenario).filter(
        WhatIfScenario.project_id == project_id
    ).order_by(WhatIfScenario.created_at.desc()).all()
