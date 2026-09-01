"""
Celery application and background tasks for Clarix.

Enables asynchronous, queued processing of large batch document ingestion and
generation jobs so they don't block the FastAPI request thread.

Enable by setting:
    CELERY_BROKER_URL=redis://localhost:6379/0
    CELERY_RESULT_BACKEND=redis://localhost:6379/0

When the broker URL is unset, the module degrades gracefully (workers and the
in-process eager mode allow synchronous execution for local dev and tests).
"""

import os
import logging
from typing import Dict, Any, List


logger = logging.getLogger(__name__)

BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip()
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip()

try:
    from celery import Celery
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False
    Celery = None  # type: ignore


def build_celery_app() -> "Celery":
    celery = Celery(
        "clarix",
        backend=RESULT_BACKEND or "rpc://",
        broker=BROKER_URL or "memory://",
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        # Run in-process synchronously when there's no real broker (dev/test).
        task_always_eager=not BROKER_URL,
        task_eager_propagates=False,
    )
    return celery


if HAS_CELERY:
    app = build_celery_app()
else:
    app = None


if HAS_CELERY:

    @app.task(name="clarix.batch_ingest_documents")
    def batch_ingest_documents_task(
        project_id: str,
        document_ids: List[str],
        actor_id: str,
        framework: str = "SFDR",
    ) -> Dict[str, Any]:
        """
        Background task that parses, chunks, extracts evidence for, and drafts
        answers for a batch of documents. Runs via Celery worker; eager mode
        (no broker) executes synchronously.
        """
        from sqlalchemy.orm import Session
        from app.database import SessionLocal
        from app.models import Document
        from app.services.ingestion import IngestionService
        from app.services.audit import write_audit_log

        db: Session = SessionLocal()
        results = []
        try:
            for doc_id in document_ids:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if not doc:
                    results.append({"document_id": doc_id, "status": "not_found"})
                    continue
                try:
                    from app.services.storage import get_storage_backend
                    storage = get_storage_backend()
                    raw = storage.load(doc.storage_url.replace("s3://", "") if doc.storage_url.startswith("s3://") else doc.storage_url)
                    pages = IngestionService.process_document_bytes(raw, doc.file_type)
                    chunks = IngestionService.chunk_document_data(pages)
                    results.append({
                        "document_id": doc_id,
                        "file_name": doc.file_name,
                        "status": "parsed",
                        "chunks": len(chunks),
                    })
                    doc.parsed_status = "Completed"
                    db.commit()
                except Exception as e:  # noqa: BLE001
                    logger.error("Batch ingest failed for doc %s: %s", doc_id, e)
                    doc.parsed_status = "Failed"
                    db.commit()
                    results.append({"document_id": doc_id, "status": "failed", "error": str(e)})

            write_audit_log(
                db,
                entity_type="project",
                entity_id=project_id,
                action="batch_ingest",
                actor_id=actor_id,
                project_id=project_id,
                payload={"document_ids": document_ids, "results": results},
            )
            db.commit()
            return {"project_id": project_id, "status": "completed", "results": results}
        finally:
            db.close()
else:
    batch_ingest_documents_task = None
