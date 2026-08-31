import os
import tempfile
import csv
import json
import io
import zipfile
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ReportingProject, Document, AuditLog, AuditorLedgerEntry, User
)
from app.auth import get_current_user, require_role
from app.services.export import ExportService
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/projects/{project_id}/export/markdown")
def download_markdown_package(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download an audit-ready Markdown disclosure package."""
    try:
        report = ExportService.generate_markdown_report(db, project_id)
        return PlainTextResponse(content=report, headers={
            "Content-Disposition": f"attachment; filename=SFDR_Disclosure_Package_{project_id}.md"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/export/html")
def download_html_package(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download a stunningly designed printable HTML audit disclosure package."""
    try:
        report = ExportService.generate_html_report(db, project_id)
        return HTMLResponse(content=report, headers={
            "Content-Disposition": f"attachment; filename=SFDR_RTS_Report_{project_id}.html"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/audit-export")
def generate_audit_export_package(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator"))
):
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        # Create a temp zip file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        zip_path = temp_zip.name
        temp_zip.close()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Final reports
            try:
                markdown_report = ExportService.generate_markdown_report(db, project_id)
                zip_file.writestr("Final_Report.md", markdown_report)
            except Exception as e:
                zip_file.writestr("Final_Report.md", f"Error generating report: {e}")

            try:
                html_report = ExportService.generate_html_report(db, project_id)
                zip_file.writestr("Final_Report.html", html_report)
            except Exception as e:
                zip_file.writestr("Final_Report.html", f"Error generating report: {e}")

            # 2. Add source documents
            documents = db.query(Document).filter(Document.project_id == project_id).all()
            integrity_report = {}
            for doc in documents:
                file_path = doc.storage_url
                if file_path and os.path.exists(file_path):
                    zip_file.write(file_path, arcname=f"sources/{doc.file_name}")
                
                integrity_info = IngestionService.verify_document_integrity(doc.id, db)
                integrity_report[doc.id] = {
                    "file_name": doc.file_name,
                    "stored_hash": integrity_info.get("stored_hash"),
                    "current_hash": integrity_info.get("current_hash"),
                    "status": integrity_info.get("integrity_status"),
                    "hashed_at": integrity_info.get("hashed_at").isoformat() if integrity_info.get("hashed_at") else None
                }

            zip_file.writestr("integrity_report.json", json.dumps(integrity_report, indent=4))

            # 3. Add evidence_mapping.csv
            ledger_entries = db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.project_id == project_id).all()
            
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow([
                "ledger_entry_id", "field_code", "field_label", "reported_value",
                "source_document", "source_page", "source_passage", "document_hash",
                "approver", "approval_timestamp"
            ])
            for entry in ledger_entries:
                field_code_val = entry.regulation_field.field_code if entry.regulation_field else ""
                field_label_val = entry.regulation_field.field_label if entry.regulation_field else ""
                doc_name_val = entry.document.file_name if entry.document else ""
                approver_name_val = entry.approved_by.username if entry.approved_by else ""
                
                writer.writerow([
                    entry.id, field_code_val, field_label_val, entry.final_value or "",
                    doc_name_val, entry.source_page or "", entry.source_passage or "",
                    entry.document_hash or "", approver_name_val,
                    entry.approval_timestamp.isoformat() if entry.approval_timestamp else ""
                ])
            zip_file.writestr("evidence_mapping.csv", csv_buffer.getvalue())

            # 4. Add audit_log.csv
            logs = db.query(AuditLog).filter(AuditLog.project_id == project_id).all()
            log_buffer = io.StringIO()
            log_writer = csv.writer(log_buffer)
            log_writer.writerow(["log_id", "entity_type", "entity_id", "action", "actor", "timestamp", "payload"])
            for log in logs:
                actor_username = "system"
                if log.actor_id:
                    user = db.query(User).filter(User.id == log.actor_id).first()
                    if user:
                        actor_username = user.username
                
                log_writer.writerow([
                    log.id, log.entity_type, log.entity_id, log.action, actor_username,
                    log.created_at.isoformat() if log.created_at else "",
                    json.dumps(log.payload) if log.payload else ""
                ])
            zip_file.writestr("audit_log.csv", log_buffer.getvalue())

        return FileResponse(
            path=zip_path,
            filename=f"Audit_Export_Package_{project_id}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
