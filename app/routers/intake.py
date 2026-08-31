"""
Data Intake Router — Investee and supply chain data portal endpoints.
"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReportingProject, DataIntakeRequest, User
from app.auth import get_current_user, require_role
from app.services.intake import DataIntakeService
from app.limiter import limiter

router = APIRouter(tags=["intake"])


class CreateIntakeRequestModel(BaseModel):
    target_company_name: str = Field(..., description="Name of portfolio company or supplier")
    target_company_email: Optional[str] = Field(None, description="Contact email for automated invitation")
    requested_framework: str = Field("SFDR", description="Framework to collect data for (SFDR, CSRD, SEC, UK_SDR)")
    requested_field_codes: Optional[List[str]] = Field(None, description="List of specific field codes requested")
    expiry_days: int = Field(30, description="Number of days before link expires")


# ---------------------------------------------------------------------------
# Authenticated Management Endpoints (Compliance Officers / Reviewers)
# ---------------------------------------------------------------------------

@router.post("/api/projects/{project_id}/intake-requests")
def create_intake_request(
    project_id: str,
    payload: CreateIntakeRequestModel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an authenticated, secure single-use intake portal link for an external supplier or portfolio company.
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    req = DataIntakeService.create_request(
        db,
        project_id=project_id,
        organization_id=project.organization_id,
        target_company_name=payload.target_company_name,
        target_company_email=payload.target_company_email,
        requested_framework=payload.requested_framework,
        requested_field_codes=payload.requested_field_codes,
        expiry_days=payload.expiry_days,
        created_by_user_id=current_user.id,
    )

    portal_url = f"/intake/{req.token}"

    return {
        "message": "Intake portal request created successfully.",
        "request_id": req.id,
        "token": req.token,
        "portal_url": portal_url,
        "target_company_name": req.target_company_name,
        "expires_at": req.expires_at.isoformat(),
        "status": req.status,
    }


@router.get("/api/projects/{project_id}/intake-requests")
def list_intake_requests(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all pending and received intake requests for a given project.
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    requests = db.query(DataIntakeRequest).filter(
        DataIntakeRequest.project_id == project_id
    ).order_by(DataIntakeRequest.created_at.desc()).all()

    results = []
    for r in requests:
        submissions = [
            {
                "id": s.id,
                "company_name": s.company_name,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "status": s.status,
                "has_file": bool(s.uploaded_file_name),
                "file_name": s.uploaded_file_name,
                "submitted_values": s.submitted_values,
                "parsed_evidence": s.parsed_evidence,
            }
            for s in r.submissions
        ]
        results.append({
            "id": r.id,
            "token": r.token,
            "target_company_name": r.target_company_name,
            "target_company_email": r.target_company_email,
            "requested_framework": r.requested_framework,
            "requested_field_codes": r.requested_field_codes,
            "status": r.status,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "submissions": submissions,
        })
    return results


@router.post("/api/intake/submissions/{submission_id}/merge")
def merge_investee_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """
    Merge verified investee submission data directly into the project's compliance matrix.
    """
    try:
        result = DataIntakeService.merge_submission(
            db,
            submission_id=submission_id,
            reviewer_id=current_user.id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Public Unauthenticated External Portal Endpoints (For Investees / Suppliers)
# ---------------------------------------------------------------------------

@router.get("/api/intake/{token}")
def get_public_intake_form(token: str, db: Session = Depends(get_db)):
    """
    Public endpoint for the external investee portal to fetch requested metrics and instructions.
    """
    try:
        details = DataIntakeService.get_public_request_details(db, token)
        return details
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/intake/{token}/submit")
@limiter.limit("10/minute")
async def submit_investee_data(
    request: Request,
    token: str,
    company_name: str = Form(...),
    contact_name: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    metrics_json: Optional[str] = Form(None),  # JSON string of submitted metrics
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Public submission endpoint: external suppliers submit structured metrics or upload proof reports.
    """
    submitted_values = {}
    if metrics_json:
        try:
            submitted_values = json.loads(metrics_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in metrics_json parameter.")

    file_bytes = None
    file_name = None
    if file:
        file_bytes = await file.read()
        file_name = file.filename

    try:
        submission = DataIntakeService.process_investee_submission(
            db,
            token=token,
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            submitted_values=submitted_values,
            file_bytes=file_bytes,
            file_name=file_name,
        )
        return {
            "message": "ESG disclosure data submitted successfully.",
            "submission_id": submission.id,
            "status": submission.status,
            "parsed_metrics_count": len(submission.parsed_evidence or {}),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
