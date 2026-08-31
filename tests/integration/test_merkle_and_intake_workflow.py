"""
Integration tests for Merkle Audit Ledger and Investee Intake Portal Workflows.
"""

import os
import sys

from app.models import Document

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestMerkleAuditWorkflow:
    """End-to-end API testing of Merkle tree proofs and auditor certificates."""

    def test_merkle_tree_and_root_endpoints(self, client, auth_headers, test_project):
        # 1. Fetch Merkle tree
        resp = client.get(f"/api/projects/{test_project.id}/merkle-tree", headers=auth_headers)
        assert resp.status_code == 200
        tree = resp.json()
        assert "merkle_root" in tree
        assert "leaves" in tree

        # 2. Fetch Merkle root summary
        resp_root = client.get(f"/api/projects/{test_project.id}/merkle-root", headers=auth_headers)
        assert resp_root.status_code == 200
        root_data = resp_root.json()
        assert root_data["current_merkle_root"] == tree["merkle_root"]

    def test_seal_checkpoint_and_export_certificate(self, client, auth_headers, test_project):
        # 1. Seal a checkpoint
        resp_cp = client.post(
            f"/api/projects/{test_project.id}/merkle-checkpoint",
            json={"checkpoint_type": "AuditSignOff"},
            headers=auth_headers,
        )
        assert resp_cp.status_code == 200
        cp_data = resp_cp.json()
        assert "checkpoint_id" in cp_data

        # 2. Export verification certificate
        resp_cert = client.get(f"/api/projects/{test_project.id}/merkle-certificate", headers=auth_headers)
        assert resp_cert.status_code == 200
        cert = resp_cert.json()
        assert cert["certificate_id"].startswith("CERT-CLARIX-")
        assert cert["project"]["id"] == test_project.id

    def test_auditor_verify_proof_endpoint(self, client, auth_headers, test_project, db_session):
        # Add a source document to generate leaves
        doc = Document(
            id="doc_audit_verify",
            project_id=test_project.id,
            file_name="verified_esg_report.pdf",
            file_type="pdf",
            storage_url="/tmp/verified_esg_report.pdf",
            file_hash="11223344556677889900aabbccddeeff",
            source_type="annual_report",
        )
        db_session.add(doc)
        db_session.commit()

        # Fetch tree to get a leaf and proof
        resp = client.get(f"/api/projects/{test_project.id}/merkle-tree", headers=auth_headers)
        tree = resp.json()
        assert len(tree["leaves"]) >= 1

        target_leaf = tree["leaves"][0]
        verify_payload = {
            "leaf_hash": target_leaf["leaf_hash"],
            "proof": target_leaf["proof"],
            "root_hash": tree["merkle_root"],
        }

        # Verify through the public auditor endpoint
        resp_verify = client.post("/api/auditor/verify-proof", json=verify_payload)
        assert resp_verify.status_code == 200
        result = resp_verify.json()
        assert result["verified"] is True
        assert "authentic and untampered" in result["message"]


class TestInvesteeIntakeWorkflow:
    """End-to-end API testing of tokenized investee data intake and merging."""

    def test_intake_lifecycle(self, client, auth_headers, test_project):
        # 1. Compliance officer generates intake request
        create_resp = client.post(
            f"/api/projects/{test_project.id}/intake-requests",
            json={
                "target_company_name": "SolarTech Global",
                "target_company_email": "esg@solartech.com",
                "requested_framework": "SFDR",
                "requested_field_codes": ["PAI_GHG_SCOPE1"],
                "expiry_days": 30,
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 200
        req_data = create_resp.json()
        token = req_data["token"]
        assert token is not None

        # 2. External investee visits public intake link
        public_resp = client.get(f"/api/intake/{token}")
        assert public_resp.status_code == 200
        public_data = public_resp.json()
        assert public_data["target_company_name"] == "SolarTech Global"

        # 3. External investee submits data
        submit_resp = client.post(
            f"/api/intake/{token}/submit",
            data={
                "company_name": "SolarTech Global",
                "contact_name": "Anna Schmidt",
                "contact_email": "anna@solartech.com",
                "metrics_json": '{"PAI_GHG_SCOPE1": {"value": 1150.0, "unit": "tCO2e"}}',
            },
        )
        assert submit_resp.status_code == 200
        sub_data = submit_resp.json()
        submission_id = sub_data["submission_id"]
        assert submission_id is not None

        # 4. Compliance officer reviews and merges submission into project
        merge_resp = client.post(
            f"/api/intake/submissions/{submission_id}/merge",
            headers=auth_headers,
        )
        assert merge_resp.status_code == 200
        merge_data = merge_resp.json()
        assert "PAI_GHG_SCOPE1" in merge_data["merged_fields"]
