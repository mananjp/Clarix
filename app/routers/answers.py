import uuid
import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    ReportingProject, FieldAnswer, FieldEvidence, DocumentChunk, Document,
    AuditorLedgerEntry, AuditLog, User, AnswerStatus
)
from app.schemas import FieldAnswerUpdate
from app.auth import get_current_user, require_role
from app.services.validation import ValidationService

router = APIRouter(prefix="/api/answers", tags=["answers"])


def _verify_answer_org(answer, current_user, db):
    """Helper to verify the answer's project belongs to the current user's org."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == answer.project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied: answer belongs to another organization.")
    return project


@router.put("/{answer_id}")
def update_answer(answer_id: str, update_in: FieldAnswerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Allows reviewers to manually override and edit a generated disclosure draft, creating a new version."""
    orig_answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not orig_answer:
        raise HTTPException(status_code=404, detail="Disclosure draft segment not found.")

    _verify_answer_org(orig_answer, current_user, db)

    # Find and update all versions to not latest
    existing_answers = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == orig_answer.project_id,
        FieldAnswer.regulation_field_id == orig_answer.regulation_field_id
    ).all()

    for ea in existing_answers:
        ea.is_latest = False

    next_version = len(existing_answers) + 1

    # Check that reviewer exists if user ID is passed
    approver_id = update_in.approved_by_user_id
    if approver_id:
        user = db.query(User).filter(User.id == approver_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    new_answer = FieldAnswer(
        id=str(uuid.uuid4()),
        project_id=orig_answer.project_id,
        regulation_field_id=orig_answer.regulation_field_id,
        answer_json=update_in.answer_json if update_in.answer_json is not None else orig_answer.answer_json,
        answer_text=update_in.answer_text,
        status=update_in.status,
        model_name=orig_answer.model_name,
        version_no=next_version,
        is_latest=True,
        regulation_version=orig_answer.regulation_version,
        prompt_version=orig_answer.prompt_version,
        model_parameters=orig_answer.model_parameters,
        approved_by=approver_id
    )
    db.add(new_answer)
    db.commit()

    # Run validation immediately to clear/update error markers
    ValidationService.validate_project(db, orig_answer.project_id)
    
    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=new_answer.id,
        action="manual_edit",
        actor_id=approver_id or "system",
        project_id=orig_answer.project_id,
        payload={"new_status": update_in.status, "version": next_version}
    )
    db.add(audit)
    db.commit()

    return {"message": "New answer version created and re-validated.", "answer_id": new_answer.id}


@router.post("/{answer_id}/approve")
def approve_disclosure_answer(answer_id: str, reviewer_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_role("ComplianceOfficer", "Administrator"))):
    """Approve a draft disclosure field, flagging it as compliance-ready."""
    answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")

    _verify_answer_org(answer, current_user, db)

    if reviewer_id:
        user = db.query(User).filter(User.id == reviewer_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    answer.status = AnswerStatus.APPROVED.value
    answer.approved_by = reviewer_id
    db.commit()

    # Create Auditor Ledger Entry
    try:
        evidence = db.query(FieldEvidence).filter(
            FieldEvidence.regulation_field_id == answer.regulation_field_id,
            FieldEvidence.project_id == answer.project_id
        ).first()

        doc_hash = None
        doc_id = None
        source_passage = None
        source_page = None
        if evidence:
            source_passage = evidence.source_locator.get("quote") if evidence.source_locator else None
            source_page = evidence.source_locator.get("page") if evidence.source_locator else None
            
            if evidence.document_chunk_id:
                chunk = db.query(DocumentChunk).filter(DocumentChunk.id == evidence.document_chunk_id).first()
                if chunk:
                    doc_id = chunk.document_id
                    doc = db.query(Document).filter(Document.id == chunk.document_id).first()
                    if doc:
                        doc_hash = doc.file_hash

        # Remove duplicate ledger entries for the same answer
        db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.field_answer_id == answer.id).delete()

        ledger_entry = AuditorLedgerEntry(
            id=str(uuid.uuid4()),
            project_id=answer.project_id,
            regulation_field_id=answer.regulation_field_id,
            field_answer_id=answer.id,
            evidence_id=evidence.id if evidence else None,
            document_id=doc_id,
            document_hash=doc_hash,
            source_passage=source_passage,
            source_page=source_page,
            extraction_model=answer.model_name or "system",
            extraction_timestamp=answer.generated_at,
            approved_by_user_id=reviewer_id or current_user.id,
            approval_timestamp=datetime.datetime.utcnow(),
            final_value=answer.answer_text,
            integrity_verified=True,
            ledger_created_at=datetime.datetime.utcnow()
        )
        db.add(ledger_entry)
        db.commit()
    except Exception as e:
        logging.error("Error creating auditor ledger entry: %s", e)

    # If all latest fields in project are approved, mark project as completed
    project_id = answer.project_id
    total_fields = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.is_latest == True
    ).count()
    approved_fields = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.is_latest == True,
        FieldAnswer.status == AnswerStatus.APPROVED.value
    ).count()

    if total_fields == approved_fields:
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        project.status = "Completed"
        db.commit()

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=answer_id,
        action="approve",
        actor_id=reviewer_id or current_user.id,
        project_id=project_id
    )
    db.add(audit)
    db.commit()

    return {"message": "Disclosure approved."}


@router.post("/{answer_id}/reject")
def reject_disclosure_answer(answer_id: str, reviewer_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_role("ComplianceOfficer", "Administrator"))):
    """Reject a draft disclosure field, pushing it back to draft status."""
    answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")

    _verify_answer_org(answer, current_user, db)

    if reviewer_id:
        user = db.query(User).filter(User.id == reviewer_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    answer.status = AnswerStatus.REJECTED.value
    answer.approved_by = None
    db.commit()

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=answer_id,
        action="reject",
        actor_id=reviewer_id or "system",
        project_id=answer.project_id
    )
    db.add(audit)
    db.commit()

    return {"message": "Disclosure rejected."}
