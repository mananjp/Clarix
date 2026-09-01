"""
ESG Data Feed Router — third-party investee ESG metric ingestion.

Lets compliance officers pull investee-company ESG metrics from external data
vendors (Sustainalytics / MSCI) to fill the SFDR PAI data-availability gap, and
optionally push them into a tokenized intake request as a pre-populated feed.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.services.esg_data_feed import ESGDataFeedService

router = APIRouter(prefix="/api/esg-feed", tags=["esg-feed"])


class FeedRequest(BaseModel):
    isin: str = Field(..., description="ISIN of the investee company")
    framework: str = Field("SFDR", description="Framework to collect for (SFDR, CSRD)")
    requested_fields: Optional[List[str]] = Field(None, description="Specific field codes")


@router.post("/company/fetch")
def fetch_company_esg_data(
    payload: FeedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """Fetch investee ESG metrics from the configured third-party data provider."""
    result = ESGDataFeedService.fetch_for_company(
        db,
        isin=payload.isin,
        framework=payload.framework,
        requested_fields=payload.requested_fields,
    )
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "ESG feed unavailable."))
    return result


@router.get("/fields")
def list_requestable_fields(
    framework: str = "SFDR",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator", "Reviewer")),
):
    """List the numeric field codes requestable from the ESG feed for a framework."""
    return {"framework": framework, "fields": ESGDataFeedService.resolve_field_codes(db, framework)}
