"""
Auditor-facing assurance service.

Provides read-only, scoped access to project evidence trails, auditor ledger
entries, document integrity verification, and assurance-pack export. Auditors
(ISAE 3000 / ISAE 3410 limited-assurance providers) should be able to inspect
the full audit trail without being able to modify any disclosure content.
"""

import csv
import io
import logging
import zipfile
import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from app.models import (
    ReportingProject, AuditorLedgerEntry, FieldAnswer,
    Document, MerkleAuditCheckpoint, RegulationField, AuditLog,
)

logger = logging.getLogger(__name__)


class AuditorService:
    """Read-only assurance data assembly for external/independent auditors."""

    # ------------------------------------------------------------------
    # 1. Evidence trail
    # ------------------------------------------------------------------
    @staticmethod
    def get_evidence_trail(db: Session, project_id: str) -> List[Dict[str, Any]]:
        """
        Return the full evidence-and-approval trail for a project, scoped to
        ledger entries. Purely read-only: nothing is mutated here.
        """
        entries = (
            db.query(AuditorLedgerEntry)
            .filter(AuditorLedgerEntry.project_id == project_id)
            .order_by(AuditorLedgerEntry.ledger_created_at.asc())
            .all()
        )

        trail = []
        for e in entries:
            trail.append({
                "ledger_entry_id": e.id,
                "field_code": e.regulation_field.field_code if e.regulation_field else None,
                "field_label": e.regulation_field.field_label if e.regulation_field else None,
                "final_value": e.final_value,
                "source_document": e.document.file_name if e.document else None,
                "document_hash": e.document_hash,
                "source_page": e.source_page,
                "source_passage": e.source_passage,
                "extraction_model": e.extraction_model,
                "extraction_timestamp": e.extraction_timestamp.isoformat() if e.extraction_timestamp else None,
                "approver": e.approved_by.username if e.approved_by else None,
                "approval_timestamp": e.approval_timestamp.isoformat() if e.approval_timestamp else None,
                "integrity_verified": e.integrity_verified,
            })
        return trail

    # ------------------------------------------------------------------
    # 2. Document integrity status
    # ------------------------------------------------------------------
    @staticmethod
    def get_document_integrity(db: Session, project_id: str) -> List[Dict[str, Any]]:
        """Return the hash-integrity status of every source document in a project."""
        docs = db.query(Document).filter(Document.project_id == project_id).all()
        return [
            {
                "document_id": d.id,
                "file_name": d.file_name,
                "stored_hash": d.file_hash,
                "hash_algorithm": d.hash_algorithm,
                "hashed_at": d.hashed_at.isoformat() if d.hashed_at else None,
                "integrity_status": "INTACT" if d.file_hash else "NOT_HASHED",
            }
            for d in docs
        ]

    # ------------------------------------------------------------------
    # 3. Merkle checkpoints (immutable scope)
    # ------------------------------------------------------------------
    @staticmethod
    def get_merkle_checkpoints(db: Session, project_id: str) -> List[Dict[str, Any]]:
        cps = (
            db.query(MerkleAuditCheckpoint)
            .filter(MerkleAuditCheckpoint.project_id == project_id)
            .order_by(MerkleAuditCheckpoint.sealed_at.desc())
            .all()
        )
        return [
            {
                "checkpoint_id": cp.id,
                "merkle_root": cp.merkle_root,
                "leaf_count": cp.leaf_count,
                "checkpoint_type": cp.checkpoint_type,
                "sealed_by": cp.sealed_by.username if cp.sealed_by else "system",
                "sealed_at": cp.sealed_at.isoformat() if cp.sealed_at else None,
            }
            for cp in cps
        ]

    # ------------------------------------------------------------------
    # 4. Full audit activity for the project
    # ------------------------------------------------------------------
    @staticmethod
    def get_audit_activity(db: Session, project_id: str) -> List[Dict[str, Any]]:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.project_id == project_id)
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        return [
            {
                "log_id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "actor": log.actor.username if log.actor else "system",
                "payload": log.payload,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    # ------------------------------------------------------------------
    # 5. Assurance-pack export (zip of evidence + ledger + integrity)
    # ------------------------------------------------------------------
    @staticmethod
    def build_assurance_pack(db: Session, project_id: str) -> Dict[str, Any]:
        """
        Assemble the immutable materials an auditor needs to perform a
        limited-assurance review. Returns a dict describing the pack contents;
        the caller decides how to serialize (zip/JSON).
        """
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        trail = AuditorService.get_evidence_trail(db, project_id)
        integrity = AuditorService.get_document_integrity(db, project_id)
        checkpoints = AuditorService.get_merkle_checkpoints(db, project_id)
        activity = AuditorService.get_audit_activity(db, project_id)

        # Coverage summary: how many fields are finally approved vs total
        fields = db.query(RegulationField).filter(
            RegulationField.disclosure_type == project.disclosure_type
        ).count()
        approved = (
            db.query(FieldAnswer)
            .filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.is_latest.is_(True),
                FieldAnswer.status == "Approved",
            )
            .count()
        )

        return {
            "project_id": project_id,
            "project_name": project.name,
            "reporting_period": {
                "start": project.reporting_period_start.isoformat() if project.reporting_period_start else None,
                "end": project.reporting_period_end.isoformat() if project.reporting_period_end else None,
            },
            "status": project.status,
            "coverage": {
                "total_fields": fields,
                "approved_fields": approved,
                "approved_percentage": round((approved / fields * 100), 1) if fields else 0.0,
            },
            "evidence_entries": len(trail),
            "documents": integrity,
            "merkle_checkpoints": checkpoints,
            "audit_activity": activity,
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

    @staticmethod
    def build_assurance_zip_bytes(db: Session, project_id: str) -> bytes:
        """Serialize the assurance pack into an in-memory zip of CSV/JSON/text."""
        pack = AuditorService.build_assurance_pack(db, project_id)
        import json

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("assurance_manifest.json", json.dumps(pack, indent=4, default=str))

            # Evidence mapping CSV
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow([
                "ledger_entry_id", "field_code", "field_label", "final_value",
                "source_document", "document_hash", "source_page", "source_passage",
                "extraction_model", "approver", "approval_timestamp", "integrity_verified",
            ])
            for entry in pack.get("_ledger", []):
                pass
            # Rebuild from trail details
            trail = AuditorService.get_evidence_trail(db, project_id)
            for t in trail:
                writer.writerow([
                    t["ledger_entry_id"], t["field_code"], t["field_label"],
                    t["final_value"], t["source_document"], t["document_hash"],
                    t["source_page"], t["source_passage"], t["extraction_model"],
                    t["approver"], t["approval_timestamp"], t["integrity_verified"],
                ])
            zf.writestr("evidence_mapping.csv", out.getvalue())

            # Document integrity CSV
            out2 = io.StringIO()
            w2 = csv.writer(out2)
            w2.writerow(["document_id", "file_name", "stored_hash", "hash_algorithm", "integrity_status"])
            for d in pack["documents"]:
                w2.writerow([d["document_id"], d["file_name"], d["stored_hash"], d["hash_algorithm"], d["integrity_status"]])
            zf.writestr("document_integrity.csv", out2.getvalue())

            # Audit activity CSV
            out3 = io.StringIO()
            w3 = csv.writer(out3)
            w3.writerow(["log_id", "entity_type", "entity_id", "action", "actor", "created_at"])
            for a in pack["audit_activity"]:
                w3.writerow([a["log_id"], a["entity_type"], a["entity_id"], a["action"], a["actor"], a["created_at"]])
            zf.writestr("audit_activity.csv", out3.getvalue())

        buffer.seek(0)
        return buffer.getvalue()
