"""add_greenwashing_audit_tables

Revision ID: a1b2c3d4e5f6
Revises: e921d7b3a4c8
Create Date: 2026-08-31 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e921d7b3a4c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add greenwashing audit and findings tables."""
    op.create_table(
        'greenwashing_audits',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=True),
        sa.Column('audit_status', sa.String(), nullable=True),
        sa.Column('total_claims_extracted', sa.Integer(), nullable=True),
        sa.Column('total_findings', sa.Integer(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_greenwashing_audits_id'), 'greenwashing_audits', ['id'], unique=False)

    op.create_table(
        'greenwashing_findings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('audit_id', sa.String(), nullable=False),
        sa.Column('claim_quote', sa.Text(), nullable=False),
        sa.Column('claim_source', sa.JSON(), nullable=True),
        sa.Column('contradicting_field_code', sa.String(), nullable=True),
        sa.Column('contradicting_value', sa.JSON(), nullable=True),
        sa.Column('discrepancy_category', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=True),
        sa.Column('legal_citation', sa.Text(), nullable=True),
        sa.Column('penalty_tier', sa.String(), nullable=True),
        sa.Column('enforcement_body', sa.String(), nullable=True),
        sa.Column('remediation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['audit_id'], ['greenwashing_audits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_greenwashing_findings_id'), 'greenwashing_findings', ['id'], unique=False)


def downgrade() -> None:
    """Drop greenwashing audit and findings tables."""
    op.drop_index(op.f('ix_greenwashing_findings_id'), table_name='greenwashing_findings')
    op.drop_table('greenwashing_findings')
    op.drop_index(op.f('ix_greenwashing_audits_id'), table_name='greenwashing_audits')
    op.drop_table('greenwashing_audits')
