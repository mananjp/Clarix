"""
Health & readiness probes.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db, engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    """Liveness probe - the process is up and serving requests."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness probe - verifies DB connectivity and Groq reachability."""
    # --- Database check ---
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
        return {
            "status": "not_ready",
            "checks": {"database": db_status},
        }

    engine_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        engine_status = "error"

    # --- Groq reachability check ---
    groq_status = "unconfigured"
    try:
        from app.services.generation import GenerationService
        client = GenerationService.get_groq_client()
        if client is not None:
            groq_status = "ok"
        else:
            groq_status = "no_key"
    except Exception as exc:
        logger.warning("Groq readiness check failed: %s", exc)
        groq_status = "error"

    ready = db_status == "ok" and engine_status == "ok"
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": db_status,
            "engine": engine_status,
            "groq": groq_status,
        },
    }
