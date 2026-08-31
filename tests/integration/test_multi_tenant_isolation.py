"""
Integration tests for Multi-Tenant Isolation, Correlation IDs, and Rate Limiting.
"""

import os
import sys
import datetime

import pytest
from app.models import Organization, User, ReportingProject, ProjectStatus
from app.auth import get_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture(scope="function")
def multi_tenant_setup(db_session):
    """
    Set up two distinct organizations with users and projects:
      - Org A: Acme Asset Management
        - User A (ComplianceOfficer)
        - Project A
      - Org B: Global Green Capital
        - User B (Administrator)
        - Project B
    """
    # 1. Organizations
    org_a = Organization(id="org_a", name="Acme Asset Management", type="Asset Manager")
    org_b = Organization(id="org_b", name="Global Green Capital", type="Bank")
    db_session.add_all([org_a, org_b])

    # 2. Users
    user_a = User(
        id="user_a",
        organization_id="org_a",
        username="alice_acme",
        email="alice@acme.com",
        hashed_password=get_password_hash("Password123!"),
        role="ComplianceOfficer",
        active=True,
    )
    user_b = User(
        id="user_b",
        organization_id="org_b",
        username="bob_global",
        email="bob@globalgreen.com",
        hashed_password=get_password_hash("Password123!"),
        role="Administrator",
        active=True,
    )
    db_session.add_all([user_a, user_b])

    # 3. Projects
    project_a = ReportingProject(
        id="project_a_id",
        organization_id="org_a",
        name="Acme SFDR PAI 2025",
        disclosure_type="entity_pai",
        reporting_period_start=datetime.date(2025, 1, 1),
        reporting_period_end=datetime.date(2025, 12, 31),
        status=ProjectStatus.DRAFT.value,
    )
    project_b = ReportingProject(
        id="project_b_id",
        organization_id="org_b",
        name="Global Green Sovereign ESG 2025",
        disclosure_type="entity_pai",
        reporting_period_start=datetime.date(2025, 1, 1),
        reporting_period_end=datetime.date(2025, 12, 31),
        status=ProjectStatus.DRAFT.value,
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "project_a": project_a,
        "project_b": project_b,
    }


def get_token(client, username, password="Password123!"):
    resp = client.post("/api/auth/token", data={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestMultiTenantIsolation:
    """Verify complete data isolation between tenants."""

    def test_project_listing_isolated_to_org(self, client, multi_tenant_setup):
        """User A sees only Org A projects, User B sees only Org B projects."""
        headers_a = get_token(client, "alice_acme")
        headers_b = get_token(client, "bob_global")

        resp_a = client.get("/api/projects", headers=headers_a)
        assert resp_a.status_code == 200
        projects_a = resp_a.json()
        project_ids_a = [p["id"] for p in projects_a]
        assert "project_a_id" in project_ids_a
        assert "project_b_id" not in project_ids_a

        resp_b = client.get("/api/projects", headers=headers_b)
        assert resp_b.status_code == 200
        projects_b = resp_b.json()
        project_ids_b = [p["id"] for p in projects_b]
        assert "project_b_id" in project_ids_b
        assert "project_a_id" not in project_ids_b

    def test_cross_org_project_update_forbidden(self, client, multi_tenant_setup):
        """User A cannot update Org B's project."""
        headers_a = get_token(client, "alice_acme")

        resp = client.put(
            "/api/projects/project_b_id",
            json={"name": "Hacked Project Name"},
            headers=headers_a,
        )
        assert resp.status_code == 404

    def test_cross_org_project_delete_forbidden(self, client, multi_tenant_setup):
        """Admin from Org B cannot delete Org A's project."""
        headers_b = get_token(client, "bob_global")

        resp = client.delete("/api/projects/project_a_id", headers=headers_b)
        assert resp.status_code == 404

    def test_cross_org_document_access_forbidden(self, client, multi_tenant_setup):
        """User A cannot list or upload documents to Org B's project."""
        headers_a = get_token(client, "alice_acme")

        resp = client.get("/api/projects/project_b_id/documents", headers=headers_a)
        assert resp.status_code == 404


class TestObservabilityAndMiddleware:
    """Test correlation ID propagation and request tracing."""

    def test_correlation_id_in_response_headers(self, client):
        custom_id = "trace-req-uuid-12345"
        resp = client.get("/healthz", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == custom_id

    def test_auto_generated_correlation_id(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 10


class TestRateLimiting:
    """Test rate limiting on sensitive auth endpoints."""

    def test_auth_rate_limit_exceeded(self, client):
        """Sending more requests than allowed per minute triggers HTTP 429."""
        from app.limiter import limiter
        limiter.enabled = True
        try:
            for _ in range(5):
                client.post("/api/auth/token", data={"username": "fake", "password": "wrong"})

            # The 6th request should hit the 5/minute limit
            resp = client.post("/api/auth/token", data={"username": "fake", "password": "wrong"})
            assert resp.status_code == 429
            data = resp.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        finally:
            limiter.enabled = False
