from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import (
    ReportingProject, AuditLog, AuditorLedgerEntry, RegulationField, User
)
from app.schemas import AuditLogResponse, AuditorLedgerResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/projects/{project_id}/audit-logs", response_model=List[AuditLogResponse])
def get_project_audit_logs(project_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """Retrieve audit trail log entries for a specific reporting project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    logs = db.query(AuditLog).filter(AuditLog.project_id == project_id).order_by(AuditLog.created_at.desc()).all()
    
    results = []
    for log in logs:
        actor_username = None
        actor_role = None
        if log.actor_id:
            user = db.query(User).filter(User.id == log.actor_id).first()
            if user:
                actor_username = user.username
                actor_role = user.role
        
        results.append(AuditLogResponse(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            actor_id=log.actor_id,
            project_id=log.project_id,
            payload=log.payload,
            created_at=log.created_at,
            actor_username=actor_username,
            actor_role=actor_role
        ))
    return results


@router.get("/projects/{project_id}/auditor-ledger", response_model=List[AuditorLedgerResponse])
def get_project_auditor_ledger(
    project_id: str,
    field_code: Optional[str] = None,
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.project_id == project_id)
    
    if field_code:
        query = query.join(RegulationField).filter(RegulationField.field_code == field_code)
    elif framework:
        query = query.join(RegulationField).filter(RegulationField.framework == framework)
        
    entries = query.all()
    results = []
    for entry in entries:
        field_code_val = entry.regulation_field.field_code if entry.regulation_field else None
        field_label_val = entry.regulation_field.field_label if entry.regulation_field else None
        doc_name_val = entry.document.file_name if entry.document else None
        approver_name_val = entry.approved_by.username if entry.approved_by else None
        
        results.append(AuditorLedgerResponse(
            id=entry.id,
            project_id=entry.project_id,
            regulation_field_id=entry.regulation_field_id,
            field_answer_id=entry.field_answer_id,
            evidence_id=entry.evidence_id,
            document_id=entry.document_id,
            document_hash=entry.document_hash,
            source_passage=entry.source_passage,
            source_page=entry.source_page,
            extraction_model=entry.extraction_model,
            extraction_timestamp=entry.extraction_timestamp,
            approved_by_user_id=entry.approved_by_user_id,
            approval_timestamp=entry.approval_timestamp,
            final_value=entry.final_value,
            integrity_verified=entry.integrity_verified,
            ledger_created_at=entry.ledger_created_at,
            field_code=field_code_val,
            field_label=field_label_val,
            document_name=doc_name_val,
            approver_username=approver_name_val
        ))
    return results


@router.get("/projects/{project_id}/auditor-ledger/{field_id}", response_model=AuditorLedgerResponse)
def get_auditor_ledger_field_entry(
    project_id: str,
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entry = db.query(AuditorLedgerEntry).filter(
        AuditorLedgerEntry.project_id == project_id,
        AuditorLedgerEntry.regulation_field_id == field_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Auditor ledger entry not found for this field.")
    
    field_code_val = entry.regulation_field.field_code if entry.regulation_field else None
    field_label_val = entry.regulation_field.field_label if entry.regulation_field else None
    doc_name_val = entry.document.file_name if entry.document else None
    approver_name_val = entry.approved_by.username if entry.approved_by else None
    
    return AuditorLedgerResponse(
        id=entry.id,
        project_id=entry.project_id,
        regulation_field_id=entry.regulation_field_id,
        field_answer_id=entry.field_answer_id,
        evidence_id=entry.evidence_id,
        document_id=entry.document_id,
        document_hash=entry.document_hash,
        source_passage=entry.source_passage,
        source_page=entry.source_page,
        extraction_model=entry.extraction_model,
        extraction_timestamp=entry.extraction_timestamp,
        approved_by_user_id=entry.approved_by_user_id,
        approval_timestamp=entry.approval_timestamp,
        final_value=entry.final_value,
        integrity_verified=entry.integrity_verified,
        ledger_created_at=entry.ledger_created_at,
        field_code=field_code_val,
        field_label=field_label_val,
        document_name=doc_name_val,
        approver_username=approver_name_val
    )
