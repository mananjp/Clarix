"""
Unit tests for Audit Service & GDPR Data Retention (Phase 8).
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.models import AuditLog, User
from app.services.audit import write_audit_log, export_user_data, anonymize_user


class TestAuditService:
    def test_write_audit_log_transactional(self, db_session, seeded_db):
        """write_audit_log flushes within the caller's transaction."""
        user = db_session.query(User).first()
        log = write_audit_log(
            db_session,
            entity_type="project",
            entity_id="proj_123",
            action="create",
            actor_id=user.id,
            project_id="proj_123",
            payload={"name": "Test Project"}
        )
        assert log.id is not None
        assert log.action == "create"
        assert log.entity_type == "project"

        # Query back to verify it was flushed
        queried = db_session.query(AuditLog).filter(AuditLog.id == log.id).first()
        assert queried is not None
        assert queried.payload == {"name": "Test Project"}

    def test_export_user_data_gdpr(self, db_session, seeded_db):
        """export_user_data returns user info and associated audit logs."""
        user = db_session.query(User).first()
        write_audit_log(
            db_session,
            entity_type="document",
            entity_id="doc_1",
            action="upload",
            actor_id=user.id,
            payload={"filename": "test.pdf"}
        )
        db_session.commit()

        data = export_user_data(db_session, user.id)
        assert "user" in data
        assert data["user"]["username"] == user.username
        assert "audit_logs" in data
        assert len(data["audit_logs"]) >= 1

    def test_export_nonexistent_user(self, db_session):
        data = export_user_data(db_session, "nonexistent_user_id")
        assert "error" in data

    def test_anonymize_user_gdpr(self, db_session, seeded_db):
        """anonymize_user redacts PII and deactivates the user."""
        user = db_session.query(User).first()
        user_id = user.id

        success = anonymize_user(db_session, user_id)
        assert success is True
        db_session.commit()

        updated_user = db_session.query(User).filter(User.id == user_id).first()
        assert updated_user.active is False
        assert updated_user.hashed_password == "REDACTED"
        assert "deleted_" in updated_user.username
        assert "redacted.local" in updated_user.email
