"""
Matrix & GenAI processing router.

Provides the compliance matrix endpoint (GET /api/projects/{id}/matrix) consumed by
the frontend RequirementMatrix page, together with the "Execute GenAI" processing
endpoint (POST /api/projects/{id}/process) that extracts evidence from ingested
document chunks and drafts disclosure answers.
"""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ReportingProject, RegulationField, FieldAnswer, FieldEvidence, Document,
    DocumentChunk, ValidationResult, User, AnswerStatus, ProjectStatus,
)
from app.auth import get_current_user
from app.services.generation import GenerationService
from app.services.validation import ValidationService
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["matrix"])


def _project_or_404(db, project_id, current_user):
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _build_matrix_row(db, project, field, answer_by_field, evidence_fields, validation_failed):
    answer = answer_by_field.get(field.id)
    has_evidence = field.id in evidence_fields
    answer_status = answer.status if answer else AnswerStatus.MISSING.value
    is_valid = bool(
        answer
        and answer.is_latest
        and answer.status == AnswerStatus.APPROVED.value
        and has_evidence
        and not validation_failed.get(field.id)
    )
    return {
        "field_id": field.id,
        "field_code": field.field_code,
        "field_label": field.field_label,
        "annex_code": field.annex_code,
        "framework": field.framework,
        "disclosure_type": field.disclosure_type,
        "field_kind": field.field_kind,
        "mandatory": field.mandatory,
        "answer_status": answer_status,
        "answer_text": (answer.answer_text or "") if answer else "",
        "answer_json": (answer.answer_json or {}) if answer else {},
        "regulation_version": (answer.regulation_version or field.regulation_version) if answer else field.regulation_version,
        "penalty_tier": field.penalty_tier,
        "legal_basis": field.legal_basis,
        "enforcement_body": field.enforcement_body,
        "is_valid": bool(is_valid),
        "has_evidence": bool(has_evidence),
    }


@router.get("/projects/{project_id}/matrix")
def get_project_matrix(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the compliance matrix: regulation fields + latest answers + validation status."""
    project = _project_or_404(db, project_id, current_user)

    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project.disclosure_type,
    ).all()

    answers = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.is_latest.is_(True),
    ).all()
    answer_by_field = {a.regulation_field_id: a for a in answers}

    ev_fields = {
        e.regulation_field_id
        for e in db.query(FieldEvidence).filter(FieldEvidence.project_id == project_id).all()
    }

    failures = db.query(ValidationResult).filter(
        ValidationResult.project_id == project_id,
        ValidationResult.passed.is_(False),
    ).all()
    validation_failed = {r.regulation_field_id for r in failures if r.regulation_field_id}

    return [
        _build_matrix_row(db, project, f, answer_by_field, ev_fields, validation_failed)
        for f in fields
    ]


@router.post("/projects/{project_id}/process")
def process_project_documents(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Extract evidence from ingested chunks and draft answers for missing fields."""
    project = _project_or_404(db, project_id, current_user)

    chunks_q = (
        db.query(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .all()
    )
    if not chunks_q:
        raise HTTPException(status_code=400, detail="No documents have been ingested for this project yet. Upload a document first.")

    chunks = [
        {"page_no": c.page_no, "section_title": c.section_title, "chunk_text": c.chunk_text, "metadata": c.metadata_json or {}}
        for c in chunks_q
    ]

    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project.disclosure_type,
        RegulationField.framework == "SFDR",
    ).all()

    existing = {
        a.regulation_field_id
        for a in db.query(FieldAnswer).filter(FieldAnswer.project_id == project_id).all()
    }

    processed = 0
    for field in fields:
        evidence = GenerationService.extract_evidence(field.field_code, field.field_label, field.field_kind, chunks)

        # Guard against LLM returning a top-level array (common for table extraction)
        # or otherwise malformed evidence; normalize to a dict if possible.
        if isinstance(evidence, list):
            if evidence and all(isinstance(i, dict) for i in evidence):
                evidence_list = evidence
                evidence = {
                    "status": "found",
                    "evidence_quote": None,
                    "extracted_value": evidence_list,
                    "confidence": 0.8,
                    "reasoning_short": "Table evidence extracted by LLM.",
                }
            else:
                evidence = {"status": "missing", "extracted_value": None}
        elif not isinstance(evidence, dict):
            evidence = {"status": "missing", "extracted_value": None}

        if evidence.get("status") not in ("found", "uncertain"):
            continue

        draft = GenerationService.draft_answer(field.field_code, field.field_label, field.field_kind, evidence)
        if not isinstance(draft, dict) or not draft.get("answer_text"):
            draft = {
                "answer_text": draft.get("answer_text", "") if isinstance(draft, dict) else "Drafted disclosure pending review.",
                "answer_json": draft.get("answer_json", {}) if isinstance(draft, dict) else {},
                "model_name": "system_rules_engine",
            }

        # Persist evidence (upsert-ish: create a new evidence entry)
        db.add(FieldEvidence(
            id=str(uuid.uuid4()),
            project_id=project_id,
            regulation_field_id=field.id,
            document_chunk_id=chunks_q[0].id if chunks_q else None,
            source_locator={"page": chunks_q[0].page_no if chunks_q else 1, "method": "llm"},
            extracted_value=evidence.get("extracted_value"),
            confidence=evidence.get("confidence", 0.8),
            extraction_method="llm",
            regulation_version=field.regulation_version,
        ))

        answer_json = draft.get("answer_json") or {}
        if not isinstance(answer_json, dict):
            answer_json = {}
        extracted_value = evidence.get("extracted_value")
        if "value" not in answer_json and isinstance(extracted_value, dict):
            answer_json["value"] = extracted_value.get("value")
            answer_json["unit"] = extracted_value.get("unit")
        elif "value" not in answer_json and isinstance(extracted_value, list):
            answer_json["holdings"] = extracted_value

        if field.id in existing:
            ans = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest.is_(True),
            ).first()
            if ans:
                ans.answer_text = draft.get("answer_text", ans.answer_text)
                ans.answer_json = answer_json
                ans.status = AnswerStatus.DRAFT.value
                ans.model_name = draft.get("model_name", "system_rules_engine")
                ans.is_latest = True
        else:
            db.add(FieldAnswer(
                id=str(uuid.uuid4()),
                project_id=project_id,
                regulation_field_id=field.id,
                answer_json=answer_json,
                answer_text=draft.get("answer_text", ""),
                status=AnswerStatus.DRAFT.value,
                model_name=draft.get("model_name", "system_rules_engine"),
                version_no=1,
                is_latest=True,
                regulation_version=field.regulation_version,
            ))
            existing.add(field.id)
        processed += 1

    if processed:
        project.status = ProjectStatus.VALIDATING.value
        try:
            ValidationService.validate_project(db, project_id)
        except Exception as e:  # robust
            logger.warning("Validation failed during process (robust): %s", e)

    write_audit_log(
        db,
        entity_type="project",
        entity_id=project_id,
        action="process",
        actor_id=current_user.id,
        project_id=project_id,
        payload={"fields_processed": processed},
    )
    db.commit()

    return {"message": f"GenAI extraction & drafting complete for {processed} field(s).", "fields_processed": processed}
