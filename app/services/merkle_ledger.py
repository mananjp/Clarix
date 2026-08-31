"""
Cryptographic Merkle-Tree Audit Ledger & Verification Engine.

Provides mathematical proof of compliance data integrity for Big 4 external
auditors and regulatory authorities (ESMA, BaFin, SEC).
"""

import json
import hashlib
import uuid
import datetime
import logging
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.models import (
    ReportingProject, Document, FieldAnswer, FieldEvidence,
    AuditorLedgerEntry, MerkleAuditCheckpoint,
)

logger = logging.getLogger(__name__)


def hash_leaf(data: Any) -> str:
    """
    Hash a data payload as a Merkle tree leaf.
    Uses SHA-256 with 0x00 domain separation prefix to prevent second preimage attacks.
    """
    if isinstance(data, dict) or isinstance(data, list):
        serialized = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(data, str):
        serialized = data.encode("utf-8")
    elif isinstance(data, bytes):
        serialized = data
    else:
        serialized = str(data).encode("utf-8")

    hasher = hashlib.sha256()
    hasher.update(b"\x00")  # Leaf domain separation
    hasher.update(serialized)
    return hasher.hexdigest()


def hash_nodes(left: str, right: str) -> str:
    """
    Combine two child node hashes into a parent hash.
    Uses SHA-256 with 0x01 domain separation prefix.
    """
    hasher = hashlib.sha256()
    hasher.update(b"\x01")  # Internal node domain separation
    hasher.update(bytes.fromhex(left))
    hasher.update(bytes.fromhex(right))
    return hasher.hexdigest()


def build_merkle_tree(leaf_hashes: List[str]) -> Tuple[str, List[List[str]]]:
    """
    Construct a full binary Merkle tree from a list of leaf hashes.
    Returns (root_hash, tree_levels).
    """
    if not leaf_hashes:
        empty_root = hashlib.sha256(b"\x00empty_tree").hexdigest()
        return empty_root, [[empty_root]]

    levels = [leaf_hashes]
    current_level = leaf_hashes

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            if i + 1 < len(current_level):
                right = current_level[i + 1]
            else:
                # Odd node is paired with itself
                right = current_level[i]
            parent = hash_nodes(left, right)
            next_level.append(parent)
        levels.append(next_level)
        current_level = next_level

    root_hash = levels[-1][0]
    return root_hash, levels


def get_merkle_proof(leaf_index: int, tree_levels: List[List[str]]) -> List[Dict[str, str]]:
    """
    Generate an audit proof path for a leaf at `leaf_index`.
    """
    proof = []
    idx = leaf_index

    for level in tree_levels[:-1]:  # Exclude root level
        is_right_child = idx % 2 == 1
        if is_right_child:
            sibling_idx = idx - 1
            direction = "left"
        else:
            sibling_idx = idx + 1
            direction = "right"

        if sibling_idx < len(level):
            sibling_hash = level[sibling_idx]
        else:
            # Paired with itself
            sibling_hash = level[idx]

        proof.append({"position": direction, "hash": sibling_hash})
        idx = idx // 2

    return proof


def verify_merkle_proof(leaf_hash: str, proof: List[Dict[str, str]], root_hash: str) -> bool:
    """
    Verify that `leaf_hash` belongs to the Merkle tree with `root_hash` using `proof`.
    """
    current = leaf_hash
    for step in proof:
        sibling = step["hash"]
        if step["position"] == "left":
            current = hash_nodes(sibling, current)
        else:
            current = hash_nodes(current, sibling)

    return current.lower() == root_hash.lower()


class MerkleAuditService:
    """High-level service managing project audit trees and verification certificates."""

    @classmethod
    def collect_project_leaves(cls, db: Session, project_id: str) -> List[Dict[str, Any]]:
        """
        Gathers all auditable items for a project in deterministic order:
          1. Uploaded Document Hashes
          2. Extracted Citations & Evidence
          3. Final Approved Disclosure Answers
          4. Auditor Ledger Entries
        """
        leaves = []

        # 1. Documents
        docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.id.asc()).all()
        for d in docs:
            payload = {
                "type": "document",
                "doc_id": d.id,
                "file_name": d.file_name,
                "file_hash": d.file_hash,
                "source_type": d.source_type,
                "hashed_at": d.hashed_at.isoformat() if d.hashed_at else None,
            }
            leaves.append({
                "item_id": f"doc_{d.id}",
                "category": "Source Document",
                "label": d.file_name,
                "payload": payload,
                "leaf_hash": hash_leaf(payload),
            })

        # 2. Evidence Citations
        evidences = db.query(FieldEvidence).filter(FieldEvidence.project_id == project_id).order_by(FieldEvidence.id.asc()).all()
        for e in evidences:
            payload = {
                "type": "evidence",
                "evidence_id": e.id,
                "field_id": e.regulation_field_id,
                "quote": e.source_locator.get("quote") if e.source_locator else None,
                "page": e.source_locator.get("page") if e.source_locator else None,
                "extracted_value": e.extracted_value,
                "confidence": e.confidence,
                "method": e.extraction_method,
            }
            field_code = e.regulation_field.field_code if e.regulation_field else e.regulation_field_id
            leaves.append({
                "item_id": f"evidence_{e.id}",
                "category": "Audit Citation Evidence",
                "label": f"Evidence for {field_code}",
                "payload": payload,
                "leaf_hash": hash_leaf(payload),
            })

        # 3. Approved Disclosure Answers
        answers = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.is_latest.is_(True),
        ).order_by(FieldAnswer.id.asc()).all()
        for a in answers:
            field_code = a.regulation_field.field_code if a.regulation_field else a.regulation_field_id
            payload = {
                "type": "answer",
                "answer_id": a.id,
                "field_code": field_code,
                "status": a.status,
                "version_no": a.version_no,
                "answer_text": a.answer_text,
                "answer_json": a.answer_json,
                "approved_by": a.approved_by,
                "generated_at": a.generated_at.isoformat() if a.generated_at else None,
            }
            leaves.append({
                "item_id": f"answer_{a.id}",
                "category": "Disclosure Answer",
                "label": f"Answer for {field_code} (v{a.version_no})",
                "payload": payload,
                "leaf_hash": hash_leaf(payload),
            })

        # 4. Auditor Ledger Entries
        ledger_entries = db.query(AuditorLedgerEntry).filter(
            AuditorLedgerEntry.project_id == project_id
        ).order_by(AuditorLedgerEntry.id.asc()).all()
        for l in ledger_entries:
            payload = {
                "type": "ledger_entry",
                "ledger_id": l.id,
                "field_id": l.regulation_field_id,
                "final_value": l.final_value,
                "document_hash": l.document_hash,
                "approver_id": l.approved_by_user_id,
                "approval_timestamp": l.approval_timestamp.isoformat() if l.approval_timestamp else None,
            }
            leaves.append({
                "item_id": f"ledger_{l.id}",
                "category": "Auditor Ledger Verification",
                "label": f"Ledger entry {l.id[:8]}",
                "payload": payload,
                "leaf_hash": hash_leaf(payload),
            })

        return leaves

    @classmethod
    def generate_project_tree(cls, db: Session, project_id: str) -> Dict[str, Any]:
        """
        Builds the live Merkle tree for a project and provides proof paths for each leaf.
        """
        leaves = cls.collect_project_leaves(db, project_id)
        leaf_hashes = [l["leaf_hash"] for l in leaves]
        root_hash, tree_levels = build_merkle_tree(leaf_hashes)

        for idx, leaf in enumerate(leaves):
            leaf["leaf_index"] = idx
            leaf["proof"] = get_merkle_proof(idx, tree_levels)

        return {
            "project_id": project_id,
            "merkle_root": root_hash,
            "leaf_count": len(leaves),
            "tree_depth": len(tree_levels),
            "leaves": leaves,
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

    @classmethod
    def create_checkpoint(
        cls,
        db: Session,
        project_id: str,
        user_id: Optional[str] = None,
        checkpoint_type: str = "Periodic",
    ) -> MerkleAuditCheckpoint:
        """
        Seals a cryptographic Merkle root checkpoint for permanent auditing.
        """
        tree = cls.generate_project_tree(db, project_id)
        checkpoint = MerkleAuditCheckpoint(
            id=str(uuid.uuid4()),
            project_id=project_id,
            merkle_root=tree["merkle_root"],
            leaf_count=tree["leaf_count"],
            tree_depth=tree["tree_depth"],
            checkpoint_type=checkpoint_type,
            sealed_by_user_id=user_id,
            sealed_at=datetime.datetime.utcnow(),
            summary_metadata={
                "leaf_count": tree["leaf_count"],
                "generated_at": tree["generated_at"],
            },
        )
        db.add(checkpoint)
        db.commit()
        db.refresh(checkpoint)
        logger.info(
            "Created Merkle checkpoint %s for project %s (root: %s)",
            checkpoint.id, project_id, checkpoint.merkle_root,
        )
        return checkpoint

    @classmethod
    def generate_verification_certificate(cls, db: Session, project_id: str) -> Dict[str, Any]:
        """
        Generate a verifiable Independent Auditor Cryptographic Certificate.
        """
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        tree = cls.generate_project_tree(db, project_id)
        latest_checkpoint = db.query(MerkleAuditCheckpoint).filter(
            MerkleAuditCheckpoint.project_id == project_id
        ).order_by(MerkleAuditCheckpoint.sealed_at.desc()).first()

        certificate_id = f"CERT-CLARIX-{project_id[:8].upper()}-{int(datetime.datetime.utcnow().timestamp())}"

        return {
            "certificate_id": certificate_id,
            "title": "Independent Regulatory Disclosure Cryptographic Verification Certificate",
            "issuer": "Clarix Regulatory Intelligence Engine (Cryptographic Ledger Subsystem)",
            "verification_algorithm": "SHA-256 Binary Merkle Tree (Domain-Separated)",
            "project": {
                "id": project.id,
                "name": project.name,
                "disclosure_type": project.disclosure_type,
                "reporting_period": f"{project.reporting_period_start} to {project.reporting_period_end}",
                "status": project.status,
                "organization_name": project.organization.name if project.organization else "Organization",
            },
            "cryptographic_summary": {
                "current_merkle_root": tree["merkle_root"],
                "leaf_count": tree["leaf_count"],
                "tree_depth": tree["tree_depth"],
                "latest_sealed_checkpoint_root": latest_checkpoint.merkle_root if latest_checkpoint else tree["merkle_root"],
                "sealed_at": latest_checkpoint.sealed_at.isoformat() if latest_checkpoint else tree["generated_at"],
            },
            "audit_trail_leaves": [
                {
                    "item_id": l["item_id"],
                    "category": l["category"],
                    "label": l["label"],
                    "leaf_hash": l["leaf_hash"],
                    "leaf_index": l["leaf_index"],
                    "proof_length": len(l["proof"]),
                }
                for l in tree["leaves"]
            ],
            "verification_instructions": (
                "External auditors can verify any data point by supplying the item's leaf payload "
                "and cryptographic proof path to POST /api/auditor/verify-proof."
            ),
            "issued_at": datetime.datetime.utcnow().isoformat(),
        }
