"""add_double_materiality_table

Revision ID: d67c2f0a1b2c3d4e5f6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd67c2f0a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'double_materiality_assessments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('esrs_topic', sa.String(), nullable=False),
        sa.Column('topic_name', sa.String(), nullable=False),
        sa.Column('financial_materiality', sa.Float(), nullable=True, server_default='0'),
        sa.Column('impact_materiality', sa.Float(), nullable=True, server_default='0'),
        sa.Column('material_threshold', sa.Float(), nullable=True, server_default='50'),
        sa.Column('combined_verdict', sa.String(), nullable=True, server_default='NotMaterial'),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('assessment_status', sa.String(), nullable=True, server_default='Draft'),
        sa.Column('assessed_by', sa.String(), nullable=True),
        sa.Column('assessed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assessed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'project_id', 'esrs_topic', name='uq_org_project_esrs_topic'),
    )
    op.create_index(op.f('ix_double_materiality_assessments_id'), 'double_materiality_assessments', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_double_materiality_assessments_id'), table_name='double_materiality_assessments')
    op.drop_table('double_materiality_assessments')
