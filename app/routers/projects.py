"""
Projects router — CRUD for reporting projects and products.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Product, ReportingProject, Document, RegulationField,
    FieldAnswer, AuditLog, User,
    ProjectStatus, AnswerStatus,
)
from app.schemas import (
    ReportingProjectCreate, ReportingProjectUpdate,
    ReportingProject as RPResponse, Product as ProductResponse,
)
from app.auth import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/products", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all seeded financial products."""
    return db.query(Product).filter(Product.active.is_(True)).all()


@router.get("/projects")
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve reporting projects for the current user's organization strictly."""
    if not current_user.organization_id:
        return []

    projects = db.query(ReportingProject).filter(ReportingProject.organization_id == current_user.organization_id).all()
    results = []
    
    for proj in projects:
        doc_count = db.query(Document).filter(Document.project_id == proj.id).count()
        fields_count = db.query(RegulationField).filter(RegulationField.disclosure_type == proj.disclosure_type).count()
        approved_count = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == proj.id,
            FieldAnswer.status == AnswerStatus.APPROVED.value,
            FieldAnswer.is_latest.is_(True)
        ).count()
        
        progress = 0
        if fields_count > 0:
            progress = int((approved_count / fields_count) * 100)
            
        results.append({
            "id": proj.id,
            "name": proj.name,
            "disclosure_type": proj.disclosure_type,
            "reporting_period_start": proj.reporting_period_start.isoformat() if proj.reporting_period_start else None,
            "reporting_period_end": proj.reporting_period_end.isoformat() if proj.reporting_period_end else None,
            "status": proj.status,
            "created_at": proj.created_at.isoformat() if proj.created_at else None,
            "document_count": doc_count,
            "progress": progress,
            "product_name": proj.product.name if proj.product else "Entity-Level PAI"
        })
    return results


@router.post("/projects", response_model=RPResponse)
def create_project(project_in: ReportingProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new compliance reporting project and isolate within org."""
    project_id = str(uuid.uuid4())
    org_id = project_in.organization_id or "default_org"
    
    if project_in.product_id:
        prod = db.query(Product).filter(Product.id == project_in.product_id).first()
        if not prod:
            raise HTTPException(status_code=400, detail="Specified product not found.")
            
    db_project = ReportingProject(
        id=project_id,
        organization_id=org_id,
        product_id=project_in.product_id,
        name=project_in.name,
        disclosure_type=project_in.disclosure_type,
        reporting_period_start=project_in.reporting_period_start,
        reporting_period_end=project_in.reporting_period_end,
        status=ProjectStatus.DRAFT.value
    )
    db.add(db_project)
    
    # Create empty baseline answers
    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project_in.disclosure_type,
        RegulationField.framework == "SFDR"
    ).all()
    for field in fields:
        baseline_answer = FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=project_id,
            regulation_field_id=field.id,
            status=AnswerStatus.MISSING.value,
            answer_text="",
            version_no=1,
            is_latest=True,
            regulation_version=field.regulation_version
        )
        db.add(baseline_answer)
        
    db.commit()
    db.refresh(db_project)
    
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="create",
        actor_id=current_user.id,
        project_id=project_id,
        payload={"name": db_project.name}
    )
    db.add(audit)
    db.commit()
    return db_project


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role("Administrator"))):
    """Delete a reporting project and all associated cascades with ownership check."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")
        
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}


@router.put("/projects/{project_id}", response_model=RPResponse)
def update_project(project_id: str, update_in: ReportingProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an existing compliance reporting project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    update_data = update_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    
    # Audit trail
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="update",
        actor_id=current_user.id,
        project_id=project_id,
        payload=update_data
    )
    db.add(audit)
    db.commit()
    
    return project
