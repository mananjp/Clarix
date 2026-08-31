import os
import uuid
import datetime
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List

from app.config import UPLOAD_DIR
from app.database import get_db
from app.models import (
    ReportingProject, Document, DocumentChunk, AuditLog, User
)
from app.schemas import DocumentIntegrityResponse
from app.auth import get_current_user
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/projects/{project_id}/documents")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload an ESG/sustainability report, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    doc_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"
    try:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{file_ext}")
        with open(storage_path, "wb") as f:
            f.write(content)
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
        hashed_at=datetime.datetime.utcnow()
    )
    db.add(db_doc)
    db.commit()

    # Process chunks and save
    try:
        pages_content = IngestionService.process_document(storage_path, file_ext)
        chunks = IngestionService.chunk_document_data(pages_content)
        
        for idx, chk in enumerate(chunks):
            # Generate chunk hash for deduplication
            text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

            db_chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                page_no=chk["page_no"],
                section_title=chk["section_title"],
                chunk_text=chk["chunk_text"],
                metadata_json=chk["metadata"],
                chunk_hash=text_hash,
                embedding_metadata={"char_count": len(chk["chunk_text"])}
            )
            db.add(db_chunk)
            
        db_doc.parsed_status = "Completed"
        db.commit()
    except Exception as e:
        db_doc.parsed_status = "Failed"
        db.commit()
        logging.error("Error parsing document: %s", e)
        raise HTTPException(status_code=500, detail=f"Parsing error: {e}")

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="document",
        entity_id=doc_id,
        action="upload",
        actor_id="system",
        project_id=project_id,
        payload={"file_name": file.filename}
    )
    db.add(audit)
    db.commit()

    return {"id": doc_id, "file_name": file.filename, "status": "Completed"}


@router.post("/projects/{project_id}/documents/batch")
async def upload_documents_batch(
    project_id: str,
    files: List[UploadFile] = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload multiple ESG/sustainability reports, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    uploaded_docs = []
    for file in files:
        doc_id = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"

        try:
            content = await file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            
            storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{file_ext}")
            with open(storage_path, "wb") as f:
                f.write(content)
        except Exception as e:
            logging.error("Failed to save file %s: %s", file.filename, e)
            continue

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
            hashed_at=datetime.datetime.utcnow()
        )
        db.add(db_doc)
        db.commit()

        # Process chunks and save
        try:
            pages_content = IngestionService.process_document(storage_path, file_ext)
            chunks = IngestionService.chunk_document_data(pages_content)
            
            for idx, chk in enumerate(chunks):
                text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

                db_chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    page_no=chk["page_no"],
                    section_title=chk["section_title"],
                    chunk_text=chk["chunk_text"],
                    metadata_json=chk["metadata"],
                    chunk_hash=text_hash,
                    embedding_metadata={"char_count": len(chk["chunk_text"])}
                )
                db.add(db_chunk)
                
            db_doc.parsed_status = "Completed"
            db.commit()
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Completed"})
        except Exception as e:
            db_doc.parsed_status = "Failed"
            db.commit()
            logging.error("Error parsing document %s: %s", file.filename, e)
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Failed", "error": str(e)})

        # Audit log
        audit = AuditLog(
            id=str(uuid.uuid4()),
            entity_type="document",
            entity_id=doc_id,
            action="upload",
            actor_id="system",
            project_id=project_id,
            payload={"file_name": file.filename}
        )
        db.add(audit)
        db.commit()

    return uploaded_docs


@router.get("/projects/{project_id}/documents")
def get_project_documents(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all uploaded documents for a project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return db.query(Document).filter(Document.project_id == project_id).all()


@router.get("/documents/{document_id}/integrity", response_model=DocumentIntegrityResponse)
def check_document_integrity(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = IngestionService.verify_document_integrity(document_id, db)
        return DocumentIntegrityResponse(
            document_id=result["document_id"],
            stored_hash=result["stored_hash"],
            current_hash=result["current_hash"],
            integrity_status=result["integrity_status"],
            hashed_at=result["hashed_at"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
