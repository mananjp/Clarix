"""deactivate compromised seed accounts (manan@company.com with known password)

Revision ID: b2c9d0e1a3f4
Revises: 7e9c4f0a1b2c3d4e5f6a7
Create Date: 2026-09-02

Data migration: the legacy auto-seed (app/seed_regulations.py) shipped a
Super Admin "manan@company.com" (and other demo accounts) with the hardcoded,
publicly-known password "password123". Anyone reading the public repo can log
in as that admin on any deployment that ran the old seed. This migration
deactivates those accounts so no already-deployed database keeps a usable
backdoor account. Create new production admins with:
    python scripts/create_first_admin.py
"""

import sqlalchemy as sa
from alembic import op
from typing import Sequence, Union

revision: str = "b2c9d0e1a3f4"
down_revision: Union[str, Sequence[str], None] = "7e9c4f0a1b2c3d4e5f6a7"
branch_labels = None
depends_on = None

# Legacy seed account ids (see app/seed_regulations.py DEMO_USERS + the removed
# manan@company.com entry) and the email of the compromised administrator.
COMPROMISED_IDS = [
    "system",
    "user_officer",
    "user_reviewer",
    "user_admin",
    "user_auditor",
    "user_manan",
]
COMPROMISED_EMAILS = ["manan@company.com"]


def _compromised_rows():
    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("active", sa.Boolean),
    )
    by_id = sa.or_(*(users.c.id == value for value in COMPROMISED_IDS))
    by_email = sa.or_(*(users.c.email == value for value in COMPROMISED_EMAILS))
    return users, sa.or_(by_id, by_email)


def upgrade() -> None:
    bind = op.get_bind()
    users, where = _compromised_rows()
    bind.execute(sa.update(users).where(where).values(active=False))


def downgrade() -> None:
    # NOTE: re-enabling previously compromised accounts is only safe once their
    # passwords have been rotated. Provided for symmetric rollback.
    bind = op.get_bind()
    users, where = _compromised_rows()
    bind.execute(sa.update(users).where(where).values(active=True))
