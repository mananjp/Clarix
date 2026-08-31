import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReportingProject, AuditLog, User
from app.auth import get_current_user
from app.services.cross_framework import CrossFrameworkTranslator, SUPPORTED_FRAMEWORKS

router = APIRouter(prefix="/api", tags=["cross-framework"])


class HarmonizeRequest(BaseModel):
    source_framework: str = "SFDR"
    target_frameworks: Optional[List[str]] = None


@router.get("/projects/{project_id}/cross-framework/summary")
def get_cross_framework_summary(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a multi-jurisdiction compliance matrix across all frameworks."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    equivalences = CrossFrameworkTranslator.resolve_equivalences(db, project_id)
    gaps = CrossFrameworkTranslator.detect_gaps(db, project_id)
    alignment = CrossFrameworkTranslator.generate_alignment_score(db, project_id)

    return {
        "project_id": project_id,
        "alignment_score": alignment["alignment_score"],
        "frameworks": alignment["frameworks"],
        "equivalences": equivalences,
        "gaps": gaps,
        "supported_frameworks": SUPPORTED_FRAMEWORKS,
    }


@router.post("/projects/{project_id}/cross-framework/harmonize")
def harmonize_cross_framework(
    project_id: str,
    request: HarmonizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-populate and harmonize secondary frameworks from primary disclosures."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    result = CrossFrameworkTranslator.harmonize_disclosures(
        db=db,
        project_id=project_id,
        source_framework=request.source_framework,
        target_frameworks=request.target_frameworks,
        actor_id=current_user.id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Harmonization failed."))

    # Audit trail
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        entity_type="cross_framework",
        entity_id=project_id,
        action="harmonize",
        actor_id=current_user.id,
        project_id=project_id,
        payload={
            "source_framework": request.source_framework,
            "target_frameworks": request.target_frameworks,
            "fields_harmonized": result["fields_harmonized"],
        },
    ))
    db.commit()

    return result
