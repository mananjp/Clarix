"""
Merkle Audit Router — Cryptographic proofs, root verification, and auditor certificates.
"""

from typing import List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReportingProject, User
from app.auth import get_current_user, require_role
from app.services.merkle_ledger import MerkleAuditService, verify_merkle_proof

router = APIRouter(prefix="/api", tags=["merkle-audit"])


class MerkleProofStep(BaseModel):
    position: str = Field(..., description="'left' or 'right'")
    hash: str = Field(..., description="SHA-256 hash of the sibling node")


class VerifyProofRequest(BaseModel):
    leaf_hash: str = Field(..., description="SHA-256 hash of the leaf to verify")
    proof: List[MerkleProofStep] = Field(..., description="Cryptographic audit proof path")
    root_hash: str = Field(..., description="Expected Merkle root hash")


class VerifyProofResponse(BaseModel):
    verified: bool
    leaf_hash: str
    root_hash: str
    proof_steps: int
    message: str


class CheckpointCreateRequest(BaseModel):
    checkpoint_type: str = Field("AuditSignOff", description="Reason for sealing (e.g. AuditSignOff, FilingSubmission)")


@router.get("/projects/{project_id}/merkle-tree")
def get_project_merkle_tree(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate and retrieve the complete live binary Merkle tree with proof vectors
    for all auditable project items (documents, citations, answers, ledger entries).
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    tree = MerkleAuditService.generate_project_tree(db, project_id)
    return tree


@router.get("/projects/{project_id}/merkle-root")
def get_project_merkle_root(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the current live Merkle root hash and historical checkpoints.
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    tree = MerkleAuditService.generate_project_tree(db, project_id)
    from app.models import MerkleAuditCheckpoint
    checkpoints = db.query(MerkleAuditCheckpoint).filter(
        MerkleAuditCheckpoint.project_id == project_id
    ).order_by(MerkleAuditCheckpoint.sealed_at.desc()).all()

    return {
        "project_id": project_id,
        "current_merkle_root": tree["merkle_root"],
        "leaf_count": tree["leaf_count"],
        "tree_depth": tree["tree_depth"],
        "checkpoints": [
            {
                "id": cp.id,
                "merkle_root": cp.merkle_root,
                "leaf_count": cp.leaf_count,
                "checkpoint_type": cp.checkpoint_type,
                "sealed_at": cp.sealed_at.isoformat() if cp.sealed_at else None,
                "sealed_by": cp.sealed_by.username if cp.sealed_by else "system",
            }
            for cp in checkpoints
        ],
    }


@router.post("/projects/{project_id}/merkle-checkpoint")
def create_project_merkle_checkpoint(
    project_id: str,
    payload: CheckpointCreateRequest = CheckpointCreateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ComplianceOfficer", "Administrator")),
):
    """
    Seals a permanent, immutable cryptographic checkpoint of the current compliance state.
    Restricted to Compliance Officers and Administrators.
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    checkpoint = MerkleAuditService.create_checkpoint(
        db,
        project_id=project_id,
        user_id=current_user.id,
        checkpoint_type=payload.checkpoint_type,
    )
    return {
        "message": "Cryptographic checkpoint sealed successfully.",
        "checkpoint_id": checkpoint.id,
        "merkle_root": checkpoint.merkle_root,
        "leaf_count": checkpoint.leaf_count,
        "sealed_at": checkpoint.sealed_at.isoformat(),
    }


@router.get("/projects/{project_id}/merkle-certificate")
def get_project_verification_certificate(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an official Independent Auditor Verification Certificate with
    full mathematical cryptographic proofs.
    """
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org"),
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    cert = MerkleAuditService.generate_verification_certificate(db, project_id)
    return cert


@router.post("/auditor/verify-proof", response_model=VerifyProofResponse)
def verify_audit_proof(req: VerifyProofRequest):
    """
    Public/Auditor verification endpoint: validates whether a specific data point
    belongs to a sealed Merkle root hash using mathematical SHA-256 binary proofs.
    """
    proof_dicts = [{"position": step.position, "hash": step.hash} for step in req.proof]
    is_valid = verify_merkle_proof(
        leaf_hash=req.leaf_hash,
        proof=proof_dicts,
        root_hash=req.root_hash,
    )

    if is_valid:
        msg = "Cryptographic proof verified successfully. Data point is authentic and untampered."
    else:
        msg = "Verification FAILED: Cryptographic proof path does not match the provided root."

    return VerifyProofResponse(
        verified=is_valid,
        leaf_hash=req.leaf_hash,
        root_hash=req.root_hash,
        proof_steps=len(req.proof),
        message=msg,
    )
