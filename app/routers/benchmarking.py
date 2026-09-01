"""
Benchmarking Router — peer comparison for PAI metrics.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.services.benchmarking import BenchmarkingService

router = APIRouter(prefix="/api/benchmarking", tags=["benchmarking"])


@router.get("/metric")
def benchmark_metric(
    regulation_field_id: str,
    reporting_year: int,
    industry_sector: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Benchmark a metric across the peer universe for a given year."""
    return BenchmarkingService.benchmark_metric(
        db,
        regulation_field_id=regulation_field_id,
        reporting_year=reporting_year,
        industry_sector=industry_sector,
    )


@router.get("/company/{organization_id}/metric/{regulation_field_id}")
def company_position(
    organization_id: str,
    regulation_field_id: str,
    reporting_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Position an organization's value for a metric against the peer distribution."""
    return BenchmarkingService.company_benchmark_position(
        db,
        organization_id=organization_id,
        regulation_field_id=regulation_field_id,
        reporting_year=reporting_year,
    )


@router.get("/projects/{project_id}/summary")
def project_benchmark_summary(
    project_id: str,
    reporting_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Benchmark all numeric metrics for a project's organization/year."""
    from app.models import ReportingProject
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return BenchmarkingService.summary_for_project(
        db,
        organization_id=project.organization_id,
        project_id=project_id,
        reporting_year=reporting_year,
    )
