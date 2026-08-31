"""add missing what_if_scenarios auditor_ledger metric_snapshots tables

Revision ID: c3f7a1b2d4e5
Revises: abbce384de42
Create Date: 2026-08-31 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f7a1b2d4e5'
down_revision: Union[str, Sequence[str], None] = 'abbce384de42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('what_if_scenarios',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('scenario_name', sa.String(), nullable=False),
    sa.Column('scenario_description', sa.Text(), nullable=True),
    sa.Column('parameters', sa.JSON(), nullable=True),
    sa.Column('triggered_obligations', sa.JSON(), nullable=True),
    sa.Column('legal_consequences', sa.JSON(), nullable=True),
    sa.Column('risk_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_what_if_scenarios_id'), 'what_if_scenarios', ['id'], unique=False)

    op.create_table('auditor_ledger',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('regulation_field_id', sa.String(), nullable=False),
    sa.Column('field_answer_id', sa.String(), nullable=True),
    sa.Column('evidence_id', sa.String(), nullable=True),
    sa.Column('document_id', sa.String(), nullable=True),
    sa.Column('document_hash', sa.String(64), nullable=True),
    sa.Column('source_passage', sa.Text(), nullable=True),
    sa.Column('source_page', sa.Integer(), nullable=True),
    sa.Column('extraction_model', sa.String(128), nullable=True),
    sa.Column('extraction_timestamp', sa.DateTime(), nullable=True),
    sa.Column('approved_by_user_id', sa.String(), nullable=True),
    sa.Column('approval_timestamp', sa.DateTime(), nullable=True),
    sa.Column('final_value', sa.Text(), nullable=True),
    sa.Column('integrity_verified', sa.Boolean(), nullable=True),
    sa.Column('ledger_created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['evidence_id'], ['field_evidence.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['field_answer_id'], ['field_answers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['regulation_field_id'], ['regulation_fields.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auditor_ledger_id'), 'auditor_ledger', ['id'], unique=False)

    op.create_table('metric_snapshots',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=False),
    sa.Column('regulation_field_id', sa.String(), nullable=False),
    sa.Column('reporting_year', sa.Integer(), nullable=False),
    sa.Column('value_numeric', sa.Float(), nullable=True),
    sa.Column('value_unit', sa.String(64), nullable=True),
    sa.Column('intensity_denominator', sa.Float(), nullable=True),
    sa.Column('intensity_value', sa.Float(), nullable=True),
    sa.Column('source_project_id', sa.String(), nullable=False),
    sa.Column('snapshot_created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['regulation_field_id'], ['regulation_fields.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'regulation_field_id', 'reporting_year', name='uq_org_field_year')
    )
    op.create_index(op.f('ix_metric_snapshots_id'), 'metric_snapshots', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_metric_snapshots_id'), table_name='metric_snapshots')
    op.drop_table('metric_snapshots')
    op.drop_index(op.f('ix_auditor_ledger_id'), table_name='auditor_ledger')
    op.drop_table('auditor_ledger')
    op.drop_index(op.f('ix_what_if_scenarios_id'), table_name='what_if_scenarios')
    op.drop_table('what_if_scenarios')
