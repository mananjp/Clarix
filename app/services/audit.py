"""
Audit service — transactional audit-log writes and GDPR data helpers.

All audit writes use ``db.flush()`` (not ``db.commit()``) so they
participate in the caller's transaction.  If the action's transaction
rolls back, the audit entry rolls back with it — guaranteeing atomicity.
"""

import uuid
import datetime
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User

logger = logging.getLogger(__name__)


def write_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: Optional[str] = None,
    project_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Create an ``AuditLog`` entry within the caller's transaction.

    Uses ``db.flush()`` — **not** ``db.commit()`` — so the audit row
    is part of the same transaction as the action it records.  If the
    surrounding code rolls back, the audit entry is also rolled back,
    preventing "phantom" audit entries for actions that never succeeded.
    """
    entry = AuditLog(
        id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        project_id=project_id,
        payload=payload,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(entry)
    db.flush()  # participates in caller's transaction
    logger.debug(
        "Audit log flushed: entity=%s/%s action=%s actor=%s",
        entity_type, entity_id, action, actor_id,
    )
    return entry


def export_user_data(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Collect all data associated with *user_id* for GDPR right-to-export.

    Returns a JSON-serialisable dict.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == user_id)
        .all()
    )

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "active": user.active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "audit_logs": [
            {
                "id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "project_id": log.project_id,
                "payload": log.payload,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in audit_logs
        ],
    }


def anonymize_user(db: Session, user_id: str) -> bool:
    """
    Anonymise a user record for GDPR right-to-delete.

    Replaces PII fields with placeholder values and deactivates the
    account.  Returns ``True`` if the user was found and anonymised.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False

    user.username = f"deleted_{user.id[:8]}"
    user.email = f"deleted_{user.id[:8]}@redacted.local"
    user.hashed_password = "REDACTED"
    user.active = False
    db.flush()

    logger.info("User %s anonymised (GDPR right-to-delete)", user_id)
    return True
