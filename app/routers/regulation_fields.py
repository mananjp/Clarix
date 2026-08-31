from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import RegulationField
from app.schemas import RegulationField as RegFieldResponse

router = APIRouter(prefix="/api/regulation-fields", tags=["regulation"])


@router.get("", response_model=List[RegFieldResponse])
def get_all_regulation_fields(framework: Optional[str] = None, db: Session = Depends(get_db)):
    """List all regulation fields across frameworks with legal metadata."""
    query = db.query(RegulationField)
    if framework:
        query = query.filter(RegulationField.framework == framework)
    return query.all()


@router.get("/{field_id}/cross-references")
def get_field_cross_references(field_id: str, db: Session = Depends(get_db)):
    """Get cross-framework links for a specific field, resolved to full field objects."""
    field = db.query(RegulationField).filter(RegulationField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found.")
    
    cross_refs = field.cross_references or []
    resolved = []
    for ref in cross_refs:
        linked_field = db.query(RegulationField).filter(
            RegulationField.field_code == ref.get("field_code")
        ).first()
        resolved.append({
            "framework": ref.get("framework"),
            "field_code": ref.get("field_code"),
            "relationship": ref.get("relationship"),
            "field_label": linked_field.field_label if linked_field else "Unknown",
            "legal_basis": linked_field.legal_basis if linked_field else None,
            "penalty_tier": linked_field.penalty_tier if linked_field else None,
            "annex_code": linked_field.annex_code if linked_field else None
        })
    
    return {
        "source_field": {
            "id": field.id,
            "field_code": field.field_code,
            "field_label": field.field_label,
            "framework": field.framework
        },
        "cross_references": resolved
    }
