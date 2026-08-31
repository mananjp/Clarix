import os
from fastapi import APIRouter, Depends
from typing import Dict

from app.config import GROQ_API_KEY, DEFAULT_MODEL
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


@router.post("")
def save_settings(payload: Dict[str, str], current_user: User = Depends(require_role("Administrator"))):
    """Update settings and environment variables dynamically."""
    global GROQ_API_KEY
    key = payload.get("groq_api_key", "").strip()
    if key:
        os.environ["GROQ_API_KEY"] = key
        return {"message": "API key configured successfully."}
    return {"message": "Empty key ignored."}
