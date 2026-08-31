import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReportingProject, Document, GreenwashingAudit, GreenwashingFinding, AuditLog, User
from app.auth import get_current_user
from app.services.greenwashing import GreenwashingDetector

router = APIRouter(prefix="/api", tags=["greenwashing"])


class GreenwashingAuditRequest(BaseModel):
    document_id: str


@router.post("/projects/{project_id}/greenwashing/audit")
def run_greenwashing_audit(
    project_id: str,
    audit_in: GreenwashingAuditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload/scan marketing materials against audited disclosures for greenwashing contradictions."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    document = db.query(Document).filter(
        Document.id == audit_in.document_id,
        Document.project_id == project_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found in this project.")

    audit = GreenwashingDetector.run_audit(
        db=db,
        project_id=project_id,
        document_id=document.id,
        actor_id=current_user.id,
    )

    # Audit trail
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        entity_type="greenwashing",
        entity_id=audit.id,
        action="audit",
        actor_id=current_user.id,
        project_id=project_id,
        payload={
            "document_id": document.id,
            "risk_score": audit.risk_score,
            "risk_level": audit.risk_level,
            "findings": audit.total_findings,
            "claims": audit.total_claims_extracted,
        },
    ))
    db.commit()

    findings = db.query(GreenwashingFinding).filter(
        GreenwashingFinding.audit_id == audit.id
    ).all()

    return _serialize_audit(audit, findings)


@router.get("/projects/{project_id}/greenwashing/report")
def get_greenwashing_report(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the Greenwashing Risk Score and detailed claim discrepancy matrix for a project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    audits = db.query(GreenwashingAudit).filter(
        GreenwashingAudit.project_id == project_id
    ).order_by(GreenwashingAudit.created_at.desc()).all()

    result = []
    for audit in audits:
        findings = db.query(GreenwashingFinding).filter(
            GreenwashingFinding.audit_id == audit.id
        ).all()
        result.append(_serialize_audit(audit, findings))

    return {"project_id": project_id, "audits": result}


def _serialize_audit(audit: GreenwashingAudit, findings):
    return {
        "id": audit.id,
        "project_id": audit.project_id,
        "document_id": audit.document_id,
        "audit_status": audit.audit_status,
        "total_claims_extracted": audit.total_claims_extracted,
        "total_findings": audit.total_findings,
        "risk_score": audit.risk_score,
        "risk_level": audit.risk_level,
        "summary": audit.summary,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
        "created_by": audit.created_by,
        "findings": [
            {
                "id": f.id,
                "claim_quote": f.claim_quote,
                "claim_source": f.claim_source,
                "contradicting_field_code": f.contradicting_field_code,
                "contradicting_value": f.contradicting_value,
                "discrepancy_category": f.discrepancy_category,
                "severity": f.severity,
                "legal_citation": f.legal_citation,
                "penalty_tier": f.penalty_tier,
                "enforcement_body": f.enforcement_body,
                "remediation": f.remediation,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in findings
        ],
    }
