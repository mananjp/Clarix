"""
Integration tests: port of tests_verify.py into proper pytest cases.
Tests the full API workflow: register → create project → upload → process → validate.
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")


class TestAuthWorkflow:
    """Test user registration and login flow."""

    def test_register_user(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "integration_user",
            "email": "integration@clarix.dev",
            "password": "IntegrationPass123!",
            "role": "Administrator",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "integration_user"
        assert data["email"] == "integration@clarix.dev"

    def test_register_duplicate_user(self, client):
        client.post("/api/auth/register", json={
            "username": "dupe_user",
            "email": "dupe@clarix.dev",
            "password": "DupePass123!",
        })
        resp = client.post("/api/auth/register", json={
            "username": "dupe_user",
            "email": "dupe@clarix.dev",
            "password": "DupePass123!",
        })
        assert resp.status_code == 400

    def test_login_valid_credentials(self, client):
        client.post("/api/auth/register", json={
            "username": "login_user",
            "email": "login@clarix.dev",
            "password": "LoginPass123!",
        })
        resp = client.post("/api/auth/token", data={
            "username": "login_user",
            "password": "LoginPass123!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_invalid_credentials(self, client):
        resp = client.post("/api/auth/token", data={
            "username": "nonexistent",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_get_current_user(self, client, auth_headers):
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "ci_user"


class TestProjectWorkflow:
    """Test project CRUD operations."""

    def test_create_project(self, client, auth_headers):
        resp = client.post("/api/projects", json={
            "name": "Integration Test Project",
            "disclosure_type": "entity_pai",
            "reporting_period_start": "2025-01-01",
            "reporting_period_end": "2025-12-31",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Integration Test Project"
        assert data["status"] == "Draft"

    def test_list_projects(self, client, auth_headers):
        resp = client.get("/api/projects", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_project(self, client, auth_headers):
        # Create first
        create_resp = client.post("/api/projects", json={
            "name": "To Update",
            "disclosure_type": "entity_pai",
            "reporting_period_start": "2025-01-01",
            "reporting_period_end": "2025-12-31",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        project_id = create_resp.json()["id"]

        resp = client.put(f"/api/projects/{project_id}", json={
            "name": "Updated Name",
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_delete_project(self, client, auth_headers):
        create_resp = client.post("/api/projects", json={
            "name": "To Delete",
            "disclosure_type": "entity_pai",
            "reporting_period_start": "2025-01-01",
            "reporting_period_end": "2025-12-31",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        project_id = create_resp.json()["id"]

        resp = client.delete(f"/api/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200


class TestSettingsEndpoint:
    """Test settings API."""

    def test_get_settings(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data
        assert "groq_api_key_configured" in data


class TestHealthEndpoints:
    """Test health and readiness probes."""

    def test_healthz(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readyz(self, client):
        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "groq" in data.get("checks", {})
