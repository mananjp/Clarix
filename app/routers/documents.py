import uuid
import datetime
import hashlib
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ReportingProject, Document, DocumentChunk, AuditLog, User,
)
from app.schemas import DocumentIntegrityResponse
from app.auth import get_current_user
from app.services.ingestion import IngestionService
from app.services.storage import get_storage_backend
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/projects/{project_id}/documents")
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    project_id: str,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an ESG/sustainability report, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    doc_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"
    try:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()

        storage = get_storage_backend()
        storage_path = storage.save(content, f"{doc_id}.{file_ext}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Create document record
    db_doc = Document(
        id=doc_id,
        project_id=project_id,
        file_name=file.filename,
        file_type=file_ext,
        source_type=source_type,
        storage_url=storage_path,
        parsed_status="Parsing",
        file_hash=file_hash,
        hash_algorithm="sha256",
        hashed_at=datetime.datetime.utcnow(),
    )
    db.add(db_doc)
    db.commit()

    # Process chunks and save
    try:
        pages_content = IngestionService.process_document(storage_path, file_ext)
        chunks = IngestionService.chunk_document_data(pages_content)

        for chk in chunks:
            text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

            db_chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                page_no=chk["page_no"],
                section_title=chk["section_title"],
                chunk_text=chk["chunk_text"],
                metadata_json=chk["metadata"],
                chunk_hash=text_hash,
                embedding_metadata={"char_count": len(chk["chunk_text"])},
            )
            db.add(db_chunk)

        db_doc.parsed_status = "Completed"
        db.commit()
    except Exception as e:
        db_doc.parsed_status = "Failed"
        db.commit()
        logger.error("Error parsing document: %s", e)
        raise HTTPException(status_code=500, detail=f"Parsing error: {e}")

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="document",
        entity_id=doc_id,
        action="upload",
        actor_id="system",
        project_id=project_id,
        payload={"file_name": file.filename},
    )
    db.add(audit)
    db.commit()

    return {"id": doc_id, "file_name": file.filename, "status": "Completed"}


@router.post("/projects/{project_id}/documents/batch")
@limiter.limit("5/minute")
async def upload_documents_batch(
    request: Request,
    project_id: str,
    files: List[UploadFile] = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload multiple ESG/sustainability reports, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    uploaded_docs = []
    storage = get_storage_backend()

    for file in files:
        doc_id = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"

        try:
            content = await file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            storage_path = storage.save(content, f"{doc_id}.{file_ext}")
        except Exception as e:
            logger.error("Failed to save file %s: %s", file.filename, e)
            continue

        db_doc = Document(
            id=doc_id,
            project_id=project_id,
            file_name=file.filename,
            file_type=file_ext,
            source_type=source_type,
            storage_url=storage_path,
            parsed_status="Parsing",
            file_hash=file_hash,
            hash_algorithm="sha256",
            hashed_at=datetime.datetime.utcnow(),
        )
        db.add(db_doc)
        db.commit()

        try:
            pages_content = IngestionService.process_document(storage_path, file_ext)
            chunks = IngestionService.chunk_document_data(pages_content)

            for chk in chunks:
                text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

                db_chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    page_no=chk["page_no"],
                    section_title=chk["section_title"],
                    chunk_text=chk["chunk_text"],
                    metadata_json=chk["metadata"],
                    chunk_hash=text_hash,
                    embedding_metadata={"char_count": len(chk["chunk_text"])},
                )
                db.add(db_chunk)

            db_doc.parsed_status = "Completed"
            db.commit()
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Completed"})
        except Exception as e:
            db_doc.parsed_status = "Failed"
            db.commit()
            logger.error("Error parsing document %s: %s", file.filename, e)
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Failed", "error": str(e)})

        audit = AuditLog(
            id=str(uuid.uuid4()),
            entity_type="document",
            entity_id=doc_id,
            action="upload",
            actor_id="system",
            project_id=project_id,
            payload={"file_name": file.filename},
        )
        db.add(audit)
        db.commit()

    return uploaded_docs


@router.get("/projects/{project_id}/documents")
def get_project_documents(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all uploaded documents for a project with organization boundary check."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    return db.query(Document).filter(Document.project_id == project_id).all()


@router.get("/documents/{document_id}/integrity", response_model=DocumentIntegrityResponse)
def check_document_integrity(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = IngestionService.verify_document_integrity(document_id, db)
        return DocumentIntegrityResponse(
            document_id=result["document_id"],
            stored_hash=result["stored_hash"],
            current_hash=result["current_hash"],
            integrity_status=result["integrity_status"],
            hashed_at=result["hashed_at"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
