"""
Double Materiality Router — CSRD mandatory first-step assessment.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.services.double_materiality import DoubleMaterialityService

router = APIRouter(prefix="/api/double-materiality", tags=["double-materiality"])


class ScoreRequest(BaseModel):
    financial_materiality: float = Field(..., description="0-100 impact on the undertaking")
    impact_materiality: float = Field(..., description="0-100 impact on people and planet")
    rationale: Optional[str] = Field(None)


@router.post("/organizations/{org_id}/initialize")
def initialize_materiality(
    org_id: str,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """Idempotently create ESRS topic rows for an org (optionally scoped to a project)."""
    rows = DoubleMaterialityService.initialize_topics(
        db, org_id=org_id, project_id=project_id, actor_id=current_user.id
    )
    return {
        "message": "Double-materiality assessment initialized.",
        "topics": [{"esrs_topic": r.esrs_topic, "topic_name": r.topic_name} for r in rows],
    }


@router.get("/organizations/{org_id}/summary")
def materiality_summary(
    org_id: str,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Aggregate double-materiality summary for an organization/project."""
    return DoubleMaterialityService.summary(db, org_id, project_id)


@router.post("/assessments/{assessment_id}/score")
def score_assessment(
    assessment_id: str,
    payload: ScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """Score a single ESRS topic and recompute the combined materiality verdict."""
    try:
        row = DoubleMaterialityService.score_topic(
            db,
            assessment_id=assessment_id,
            financial_materiality=payload.financial_materiality,
            impact_materiality=payload.impact_materiality,
            rationale=payload.rationale,
            actor_id=current_user.id,
        )
        return {
            "esrs_topic": row.esrs_topic,
            "topic_name": row.topic_name,
            "financial_materiality": row.financial_materiality,
            "impact_materiality": row.impact_materiality,
            "combined_verdict": row.combined_verdict,
            "assessment_status": row.assessment_status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
