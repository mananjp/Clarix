"""
Regulatory Content Router — legal metadata freshness management.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.services.regulatory_content import (
    RegulatoryContentService,
)

router = APIRouter(prefix="/api/regulatory", tags=["regulatory-content"])


class ContentUpdateRequest(BaseModel):
    framework: str = Field(..., description="Framework to update (SFDR, CSRD, ...)")
    target_regulation_version: str = Field(..., description="Version to stamp fields with")
    update_payload: Dict[str, Dict[str, Any]] = Field(
        ..., description="field_code -> {legal_basis, penalty_tier, enforcement_body, ...}"
    )
    notes: Optional[str] = Field(None)


@router.get("/instruments")
def list_instruments(
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """List known regulatory instruments and their versions."""
    return {"instruments": RegulatoryContentService.list_instruments()}


@router.get("/versions")
def current_versions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Summarize the current regulation_version breakdown across fields."""
    return {"field_version_summary": RegulatoryContentService.current_version_field_counts(db)}


@router.get("/stale")
def stale_content(
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """List fields whose legal metadata is behind the target baseline."""
    stale = RegulatoryContentService.stale_fields(db)
    if framework:
        stale = [s for s in stale if s["framework"] == framework]
    return {"stale_fields": stale, "stale_count": len(stale)}


@router.post("/update")
def apply_content_update(
    payload: ContentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """Apply a versioned legal-metadata update across a framework's fields (audited)."""
    try:
        result = RegulatoryContentService.apply_content_update(
            db,
            actor_id=current_user.id,
            framework=payload.framework,
            target_regulation_version=payload.target_regulation_version,
            update_payload=payload.update_payload,
            notes=payload.notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset/{framework}")
def reset_to_seed(
    framework: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
):
    """Reset a framework's fields to baseline seed values (Administrators only)."""
    try:
        return RegulatoryContentService.reset_to_seed(db, current_user.id, framework)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
