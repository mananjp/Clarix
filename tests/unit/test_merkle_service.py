"""
Unit tests for Cryptographic Merkle-Tree Audit Ledger (Phase 3).
"""

import os
import sys
import json

from app.models import Document, FieldAnswer, RegulationField, AuditorLedgerEntry
from app.services.merkle_ledger import (
    hash_leaf, hash_nodes, build_merkle_tree,
    get_merkle_proof, verify_merkle_proof, MerkleAuditService,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestMerkleTreePrimitives:
    def test_leaf_hashing_deterministic(self):
        data = {"metric": "Scope 1", "value": 120.5}
        h1 = hash_leaf(data)
        h2 = hash_leaf(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex string

    def test_leaf_hashing_domain_separated(self):
        """Leaf hash should differ from internal node hash of the same content."""
        data = "test_string"
        leaf_h = hash_leaf(data)
        dummy_hex = "a" * 64
        node_h = hash_nodes(dummy_hex, dummy_hex)
        assert leaf_h != node_h

    def test_single_leaf_tree(self):
        leaf = hash_leaf("single_disclosure_answer")
        root, levels = build_merkle_tree([leaf])
        assert root == leaf
        assert len(levels) == 1

    def test_even_leaves_tree(self):
        leaves = [hash_leaf(f"leaf_{i}") for i in range(4)]
        root, levels = build_merkle_tree(leaves)
        assert len(levels) == 3
        # Verify root computation manually
        p0 = hash_nodes(leaves[0], leaves[1])
        p1 = hash_nodes(leaves[2], leaves[3])
        expected_root = hash_nodes(p0, p1)
        assert root == expected_root

    def test_odd_leaves_tree(self):
        leaves = [hash_leaf(f"leaf_{i}") for i in range(3)]
        root, levels = build_merkle_tree(leaves)
        assert len(levels) == 3
        assert len(root) == 64

    def test_merkle_proof_verification_valid(self):
        leaves = [hash_leaf(f"data_point_{i}") for i in range(8)]
        root, levels = build_merkle_tree(leaves)

        for idx, leaf in enumerate(leaves):
            proof = get_merkle_proof(idx, levels)
            assert verify_merkle_proof(leaf, proof, root) is True

    def test_merkle_proof_verification_tampered_fails(self):
        leaves = [hash_leaf(f"data_point_{i}") for i in range(4)]
        root, levels = build_merkle_tree(leaves)

        proof = get_merkle_proof(0, levels)
        tampered_leaf = hash_leaf("tampered_fake_data")
        assert verify_merkle_proof(tampered_leaf, proof, root) is False


class TestMerkleAuditService:
    def test_generate_project_tree_empty(self, db_session, test_project):
        tree = MerkleAuditService.generate_project_tree(db_session, test_project.id)
        assert tree["project_id"] == test_project.id
        assert tree["merkle_root"] is not None
        assert isinstance(tree["leaves"], list)

    def test_generate_project_tree_with_data(self, db_session, test_project, seeded_db):
        # Add a document
        doc = Document(
            id="doc_m1",
            project_id=test_project.id,
            file_name="annual_esg_2025.pdf",
            file_type="pdf",
            storage_url="/tmp/annual_esg_2025.pdf",
            file_hash="a1b2c3d4e5f67890",
            source_type="annual_report",
        )
        db_session.add(doc)

        # Add an answer
        field = db_session.query(RegulationField).first()
        answer = FieldAnswer(
            id="ans_m1",
            project_id=test_project.id,
            regulation_field_id=field.id,
            status="Approved",
            version_no=1,
            is_latest=True,
            answer_text="Total Scope 1 emissions were 1,450 tCO2e.",
        )
        db_session.add(answer)

        # Add a ledger entry
        ledger = AuditorLedgerEntry(
            id="ledger_m1",
            project_id=test_project.id,
            regulation_field_id=field.id,
            final_value=json.dumps({"value": 1450.0, "unit": "tCO2e"}),
            document_hash="a1b2c3d4e5f67890",
        )
        db_session.add(ledger)
        db_session.commit()

        tree = MerkleAuditService.generate_project_tree(db_session, test_project.id)
        assert tree["leaf_count"] >= 3
        assert len(tree["merkle_root"]) == 64

        # Verify all leaf proofs
        for leaf in tree["leaves"]:
            is_valid = verify_merkle_proof(leaf["leaf_hash"], leaf["proof"], tree["merkle_root"])
            assert is_valid is True

    def test_create_checkpoint_and_certificate(self, db_session, test_project):
        checkpoint = MerkleAuditService.create_checkpoint(
            db_session,
            project_id=test_project.id,
            user_id=None,
            checkpoint_type="AuditSignOff",
        )
        assert checkpoint.id is not None
        assert checkpoint.merkle_root is not None
        assert checkpoint.checkpoint_type == "AuditSignOff"

        cert = MerkleAuditService.generate_verification_certificate(db_session, test_project.id)
        assert "certificate_id" in cert
        assert cert["cryptographic_summary"]["current_merkle_root"] is not None
        assert len(cert["audit_trail_leaves"]) == cert["cryptographic_summary"]["leaf_count"]
