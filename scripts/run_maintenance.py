"""
One-off maintenance script for multi-tenant schema repair and data backfill.

Run manually or via CI — NOT on every server boot.
Usage:
    python -m scripts.run_maintenance
"""
import sys
import os
import uuid
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Organization, User, ReportingProject, RegulationField, FieldAnswer, AnswerStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run():
    db = SessionLocal()
    try:
        # 1. Ensure default organization exists
        default_org = db.query(Organization).filter(Organization.id == "default_org").first()
        if not default_org:
            db.add(Organization(id="default_org", name="Clarix Default Organization", type="System Root"))
            db.commit()
            log.info("Seeded default_org.")

        # 2. Back-fill organizations for users
        users_without_org = db.query(User).filter(
            (User.organization_id == None) | (User.organization_id == "")
        ).all()
        for u in users_without_org:
            u.organization_id = "default_org"
        log.info("Back-filled org for %d users.", len(users_without_org))

        # 3. Repair orphaned projects and back-fill baseline answers
        projects = db.query(ReportingProject).all()
        backfilled_count = 0
        for proj in projects:
            if not proj.organization_id:
                proj.organization_id = "default_org"

            fields = db.query(RegulationField).filter(
                RegulationField.disclosure_type == proj.disclosure_type,
                RegulationField.framework == "SFDR"
            ).all()
            for field in fields:
                exists = db.query(FieldAnswer).filter(
                    FieldAnswer.project_id == proj.id,
                    FieldAnswer.regulation_field_id == field.id
                ).first()
                if not exists:
                    db.add(FieldAnswer(
                        id=str(uuid.uuid4()),
                        project_id=proj.id,
                        regulation_field_id=field.id,
                        status=AnswerStatus.MISSING.value,
                        answer_text="",
                        version_no=1,
                        is_latest=True,
                        regulation_version=field.regulation_version
                    ))
                    backfilled_count += 1

        db.commit()
        log.info("Maintenance complete. Back-filled %d baseline FieldAnswer records.", backfilled_count)
    except Exception as e:
        log.error("Maintenance failed: %s", e)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
