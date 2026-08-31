"""
Shared pytest fixtures for the Clarix test suite.
"""

import os
import sys
import uuid
import tempfile
import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Force a temp FILE-based SQLite for tests before any app imports.
# A file-backed DB (not `sqlite://` in-memory) keeps the app's global engine
# consistent, so the startup seed + per-test engines all see the same schema.
_test_db_path = os.path.join(tempfile.gettempdir(), f"clarix_test_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["NEON_URL"] = ""
os.environ["USE_POSTGRES"] = ""
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine as app_engine
from app.models import (
    Organization, ReportingProject, RegulationField, User,
)


@pytest.fixture(scope="session", autouse=True)
def _app_schema():
    """Create tables + default_org on the global app engine once (so startup seeding works)."""
    Base.metadata.create_all(bind=app_engine)
    from sqlalchemy.orm import Session as _S
    s = _S(bind=app_engine)
    try:
        if s.query(Organization).filter(Organization.id == "default_org").first() is None:
            s.add(Organization(id="default_org", name="Clarix Default Organization", type="System Root"))
            s.commit()
    finally:
        s.close()
    yield
    try:
        os.remove(_test_db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine per test using StaticPool."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provide a transactional DB session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def seeded_db(db_session):
    """
    Seed the test DB with a minimal set of data:
    - 1 organization
    - 1 user
    - 3 regulation fields
    """
    org = Organization(id="test_org", name="Test Organization")
    db_session.add(org)

    from app.auth import get_password_hash
    user = User(
        id="test_user",
        organization_id="test_org",
        username="testuser",
        email="test@clarix.dev",
        hashed_password=get_password_hash("testpassword123"),
        role="Administrator",
        active=True,
    )
    db_session.add(user)

    for i, (code, label, kind) in enumerate([
        ("PAI_GHG_SCOPE1", "Scope 1 GHG emissions", "numeric"),
        ("PAI_GHG_SCOPE2", "Scope 2 GHG emissions", "numeric"),
        ("PAI_FOSSIL_FUEL", "Fossil fuel sector exposure", "numeric"),
    ]):
        field = RegulationField(
            id=f"field_{i}",
            framework="SFDR",
            disclosure_type="entity_pai",
            annex_code="Annex I",
            field_code=code,
            field_label=label,
            field_kind=kind,
            mandatory=True,
            guidance={"description": f"Description for {label}", "unit": "tCO2e"},
            regulation_version="2022/1288",
            penalty_tier="High",
        )
        db_session.add(field)

    db_session.commit()
    return db_session


@pytest.fixture(scope="function")
def test_project(seeded_db):
    """Create a test project within the seeded DB."""
    project = ReportingProject(
        id="test_project",
        organization_id="test_org",
        name="Test Compliance Project",
        disclosure_type="entity_pai",
        reporting_period_start=datetime.date(2025, 1, 1),
        reporting_period_end=datetime.date(2025, 12, 31),
        status="Draft",
    )
    seeded_db.add(project)
    seeded_db.commit()
    return project


@pytest.fixture(scope="function")
def client(db_engine):
    """
    FastAPI TestClient with dependency overrides for the DB session.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    Session = sessionmaker(bind=db_engine)

    def _override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client):
    """
    Register a user and return auth headers with a valid Bearer token.
    """
    # Register
    client.post("/api/auth/register", json={
        "username": "ci_user",
        "email": "ci@clarix.dev",
        "password": "CIpassword123!",
        "role": "Administrator",
    })
    # Login
    resp = client.post("/api/auth/token", data={
        "username": "ci_user",
        "password": "CIpassword123!",
    })
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
