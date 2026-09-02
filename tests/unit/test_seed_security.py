"""
Unit tests for seed security hardening.

Verifies that:
  - demo user seeding never runs when ENVIRONMENT is production (or unset),
  - the compromised manan@company.com administrator is gone from the seed,
  - reference data (regulation fields) is still seeded in every environment.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.seed_regulations import (
    DEMO_USERS,
    seed_demo_users,
    seed_reference_data,
)
from app.models import Organization, RegulationField, User
from app.database import SessionLocal

DEMO_EMAILS = {u["email"] for u in DEMO_USERS}


@pytest.fixture(autouse=True)
def _clean_demo_users():
    """Remove any demo users before and after each test so ordering never matters."""

    def _purge():
        db = SessionLocal()
        try:
            db.query(User).filter(User.email.in_(DEMO_EMAILS)).delete()
            db.commit()
        finally:
            db.close()

    _purge()
    yield
    _purge()


class TestSeedGating:
    def test_manan_backdoor_not_in_demo_users(self):
        assert "manan@company.com" not in {u["email"] for u in DEMO_USERS}
        assert all("company.com" not in u["email"] for u in DEMO_USERS)

    def test_seed_demo_users_skipped_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        seed_demo_users()
        db = SessionLocal()
        try:
            seeded = db.query(User).filter(User.email.in_(DEMO_EMAILS)).all()
            assert seeded == []
        finally:
            db.close()

    def test_seed_demo_users_skipped_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        seed_demo_users()
        db = SessionLocal()
        try:
            seeded = db.query(User).filter(User.email.in_(DEMO_EMAILS)).all()
            assert seeded == []
        finally:
            db.close()

    def test_seed_demo_users_creates_dev_users(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        seed_demo_users()
        db = SessionLocal()
        try:
            seeded = db.query(User).filter(User.email.in_(DEMO_EMAILS)).all()
            assert {u.email for u in seeded} == DEMO_EMAILS
            assert all(u.active for u in seeded)
        finally:
            db.close()


class TestReferenceData:
    def test_reference_data_seeds_regulation_fields(self):
        seed_reference_data()
        db = SessionLocal()
        try:
            assert db.query(RegulationField).count() >= 30
        finally:
            db.close()

    def test_reference_data_creates_default_org(self):
        seed_reference_data()
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(Organization.id == "default_org").first()
            assert org is not None
        finally:
            db.close()
