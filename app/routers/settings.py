import os
from fastapi import APIRouter, Depends
from typing import Dict

from app.config import (
    GROQ_API_KEY, DEFAULT_MODEL,
    DATA_RESIDENCY_REGION, DATA_RESIDENCY_VENDOR, DATA_RESIDENCY_STATEMENT,
)
from app.models import User
from app.auth import require_role

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    """Retrieve API settings details (hiding sensitive keys)."""
    return {
        "groq_api_key_configured": bool(GROQ_API_KEY or os.getenv("GROQ_API_KEY")),
        "default_model": DEFAULT_MODEL,
        "environment": "Development"
    }


@router.get("/data-residency")
def get_data_residency(current_user: User = Depends(require_role("Administrator", "ComplianceOfficer"))):
    """Return the EU data residency / hosting configuration.

    EU asset managers handling EU regulatory data will ask where it is hosted.
    This surfaces a single, documentable answer from env-driven configuration.
    """
    return {
        "region": DATA_RESIDENCY_REGION,
        "vendor": DATA_RESIDENCY_VENDOR,
        "statement": DATA_RESIDENCY_STATEMENT,
        "eu_hosted": DATA_RESIDENCY_REGION.lower().startswith("eu"),
    }


@router.post("")
def save_settings(payload: Dict[str, str], current_user: User = Depends(require_role("Administrator"))):
    """Update settings and environment variables dynamically."""
    global GROQ_API_KEY
    key = payload.get("groq_api_key", "").strip()
    if key:
        os.environ["GROQ_API_KEY"] = key
        return {"message": "API key configured successfully."}
    return {"message": "Empty key ignored."}
