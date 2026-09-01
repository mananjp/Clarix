"""
Auditor Router — independent, read-only assurance access.

Auditors (ISAE 3000 limited-assurance providers) get a scoped view of the
evidence trail, ledger, document integrity, and Merkle checkpoints. The role
is strictly read-only; no mutation endpoint is exposed here.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReportingProject, User
from app.auth import require_role
from app.services.auditor import AuditorService

router = APIRouter(prefix="/api/auditor", tags=["auditor"])


def _get_scoped_project(db: Session, project_id: str, current_user: User) -> ReportingProject:
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")
    return project


@router.get("/projects/{project_id}/evidence-trail")
def auditor_evidence_trail(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Read-only evidence and approval trail for a project."""
    _get_scoped_project(db, project_id, current_user)
    return AuditorService.get_evidence_trail(db, project_id)


@router.get("/projects/{project_id}/document-integrity")
def auditor_document_integrity(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Source-document hash integrity report."""
    _get_scoped_project(db, project_id, current_user)
    return AuditorService.get_document_integrity(db, project_id)


@router.get("/projects/{project_id}/merkle-checkpoints")
def auditor_merkle_checkpoints(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Immutable cryptographic Merkle checkpoints."""
    _get_scoped_project(db, project_id, current_user)
    return AuditorService.get_merkle_checkpoints(db, project_id)


@router.get("/projects/{project_id}/audit-activity")
def auditor_audit_activity(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Full, read-only audit activity log for a project."""
    _get_scoped_project(db, project_id, current_user)
    return AuditorService.get_audit_activity(db, project_id)


@router.get("/projects/{project_id}/assurance-pack")
def auditor_assurance_pack(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Assurance manifest (evidence + integrity + coverage summary)."""
    _get_scoped_project(db, project_id, current_user)
    try:
        return AuditorService.build_assurance_pack(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projects/{project_id}/assurance-pack/download")
def auditor_assurance_pack_download(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Auditor", "Administrator", "ComplianceOfficer")),
):
    """Download the assurance pack as a zip for the auditor's own records."""
    _get_scoped_project(db, project_id, current_user)
    try:
        data = AuditorService.build_assurance_zip_bytes(db, project_id)
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=Assurance_Pack_{project_id}.zip"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
