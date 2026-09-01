"""Add invites table for company team onboarding.

Revision ID: 7e9c4f0a1b2c3d4e5f6a7
Revises: d67c2f0a1b2c3d4e5f6
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op
from typing import Sequence, Union

revision: str = '7e9c4f0a1b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'd67c2f0a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'invites',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('invited_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_invites_token', 'invites', ['token'], unique=True)
    op.create_index('ix_invites_id', 'invites', ['id'])
    op.create_index('ix_invites_organization_id', 'invites', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_invites_organization_id', table_name='invites')
    op.drop_index('ix_invites_id', table_name='invites')
    op.drop_index('ix_invites_token', table_name='invites')
    op.drop_table('invites')