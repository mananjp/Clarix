"""
Integration tests for company self-serve onboarding: register-with-company
creates a new org + Super Admin, and the invite flow lets that admin add
teammates via a one-time token.
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models import User, UserRole


def _register_company(client, org_name="SolarCraft Technologies"):
    return client.post("/api/auth/register", json={
        "username": "founder",
        "email": "founder@solarcraft.de",
        "password": "Sup3rSecret!",
        "role": "Reviewer",
        "organization_name": org_name,
    })


def _login(client, username, password):
    resp = client.post("/api/auth/token", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json().get('access_token', '')}"}


class TestCompanySignup:
    def test_company_register_creates_super_admin(self, client, db_session):
        resp = _register_company(client)
        assert resp.status_code == 200
        user = resp.json()
        assert user["role"] == UserRole.SUPER_ADMIN.value
        assert user["organization_id"] and user["organization_id"] != "default_org"

        org_user = db_session.query(User).filter(User.username == "founder").first()
        assert org_user.role == UserRole.SUPER_ADMIN.value
        assert org_user.organization_id != "default_org"

    def test_register_without_company_uses_default_org(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "solo",
            "email": "solo@clarix.dev",
            "password": "Password123!",
        })
        assert resp.status_code == 200
        assert resp.json()["organization_id"] == "default_org"
        assert resp.json()["role"] == "Reviewer"


class TestInviteFlow:
    def test_super_admin_can_invite_and_member_accepts(self, client, db_session):
        _register_company(client)
        headers = _login(client, "founder", "Sup3rSecret!")

        org_id = client.get("/api/users/me", headers=headers).json()["organization_id"]

        # Create invite
        inv = client.post(f"/api/organizations/{org_id}/invites", headers=headers, json={
            "email": "analyst@acme.com",
            "role": "ComplianceOfficer",
        })
        assert inv.status_code == 200
        token = inv.json()["token"]

        # List invites includes it
        listed = client.get(f"/api/organizations/{org_id}/invites", headers=headers)
        assert listed.status_code == 200
        assert any(i["token"] == token for i in listed.json())

        # Member accepts with the token
        acc = client.post("/api/invites/accept", json={
            "token": token,
            "username": "analyst_jane",
            "password": "AnalystPass!234",
        })
        assert acc.status_code == 200

        member = db_session.query(User).filter(User.email == "analyst@acme.com").first()
        assert member is not None
        assert member.role == "ComplianceOfficer"
        assert member.organization_id == org_id

        # New member can log in
        login = _login(client, "analyst_jane", "AnalystPass!234")
        me = client.get("/api/users/me", headers=login)
        assert me.status_code == 200
        assert me.json()["email"] == "analyst@acme.com"

    def test_invite_rejects_reuse(self, client):
        _register_company(client)
        headers = _login(client, "founder", "Sup3rSecret!")
        org_id = client.get("/api/users/me", headers=headers).json()["organization_id"]

        inv = client.post(f"/api/organizations/{org_id}/invites", headers=headers, json={
            "email": "x@acme.com",
            "role": "Reviewer",
        })
        token = inv.json()["token"]

        ok = client.post("/api/invites/accept", json={"token": token, "username": "u1", "password": "Pass1234!"})
        assert ok.status_code == 200
        again = client.post("/api/invites/accept", json={"token": token, "username": "u2", "password": "Pass1234!"})
        assert again.status_code == 400

    def test_can_invite_only_into_own_org(self, client):
        _register_company(client, "Company A")
        a_headers = _login(client, "founder", "Sup3rSecret!")
        # register a second company whose super admin uses a different login
        _register_company(client, "Company B")  # same username 'founder' -> duplicate
        # new user for B
        client.post("/api/auth/register", json={
            "username": "founder2", "email": "founder2@b.co", "password": "Secr3t!",
            "organization_name": "Company B",
        })
        b_headers = _login(client, "founder2", "Secr3t!")
        b_org = client.get("/api/users/me", headers=b_headers).json()["organization_id"]
        # A's admin cannot invite into B
        blocked = client.post(f"/api/organizations/{b_org}/invites", headers=a_headers, json={
            "email": "hacker@x.com", "role": "Reviewer",
        })
        assert blocked.status_code == 403