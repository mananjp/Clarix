"""
Integration tests: self-registration can never self-grant elevated roles.

Public registration must ignore any client-supplied role:
  - joining the shared default_org always yields Reviewer,
  - creating a company always yields Super Admin (server-assigned),
  - invite creation (an admin-only action) validates the role against the enum.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models import User, UserRole


class TestSelfServeRoleHardening:
    def test_cannot_self_grant_admin_on_default_org(self, client, db_session):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "aspiring_admin",
                "email": "aspiring@example.com",
                "password": "Str0ngPassw0rd!1",
                "role": "Administrator",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == UserRole.REVIEWER.value
        assert resp.json()["organization_id"] == "default_org"

        user = db_session.query(User).filter(User.username == "aspiring_admin").first()
        assert user is not None
        assert user.role == UserRole.REVIEWER.value

    def test_org_creator_is_server_assigned_super_admin(self, client):
        """Creating a company still grants Super Admin, regardless of client role."""
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "founder_secure",
                "email": "founder_secure@example.com",
                "password": "Str0ngPassw0rd!1",
                "role": "Reviewer",
                "organization_name": "Secure Capital GmbH",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == UserRole.SUPER_ADMIN.value
        assert resp.json()["organization_id"] != "default_org"


class TestInviteRoleValidation:
    def _create_admin(self, client):
        client.post(
            "/api/auth/register",
            json={
                "username": "invite_admin",
                "email": "invite_admin@example.com",
                "password": "Str0ngPassw0rd!1",
                "organization_name": "Role Guard Capital",
            },
        )
        token = client.post(
            "/api/auth/token",
            data={
                "username": "invite_admin",
                "password": "Str0ngPassw0rd!1",
            },
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        org_id = client.get("/api/users/me", headers=headers).json()["organization_id"]
        return org_id, headers

    def test_invite_rejects_role_outside_enum(self, client):
        org_id, headers = self._create_admin(client)
        resp = client.post(
            f"/api/organizations/{org_id}/invites",
            headers=headers,
            json={
                "email": "member@example.com",
                "role": "Hacker",
            },
        )
        assert resp.status_code == 422
        assert "role" in resp.text

    def test_invite_accepts_valid_role(self, client):
        org_id, headers = self._create_admin(client)
        resp = client.post(
            f"/api/organizations/{org_id}/invites",
            headers=headers,
            json={
                "email": "analyst@example.com",
                "role": UserRole.COMPLIANCE_OFFICER.value,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == UserRole.COMPLIANCE_OFFICER.value
