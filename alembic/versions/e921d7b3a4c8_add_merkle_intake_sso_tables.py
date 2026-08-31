"""add_merkle_intake_sso_tables

Revision ID: e921d7b3a4c8
Revises: f731f38ddb3d
Create Date: 2026-08-31 21:57:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e921d7b3a4c8'
down_revision: Union[str, Sequence[str], None] = 'f731f38ddb3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Merkle Audit Checkpoints
    op.create_table(
        'merkle_audit_checkpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('merkle_root', sa.String(), nullable=False),
        sa.Column('leaf_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tree_depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checkpoint_type', sa.String(), nullable=True, server_default='Periodic'),
        sa.Column('sealed_by_user_id', sa.String(), nullable=True),
        sa.Column('sealed_at', sa.DateTime(), nullable=False),
        sa.Column('summary_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sealed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_merkle_audit_checkpoints_id'), 'merkle_audit_checkpoints', ['id'], unique=False)
    op.create_index(op.f('ix_merkle_audit_checkpoints_merkle_root'), 'merkle_audit_checkpoints', ['merkle_root'], unique=False)

    # 2. Data Intake Requests
    op.create_table(
        'data_intake_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('target_company_name', sa.String(), nullable=False),
        sa.Column('target_company_email', sa.String(), nullable=True),
        sa.Column('requested_framework', sa.String(), nullable=True, server_default='SFDR'),
        sa.Column('requested_field_codes', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='Pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['reporting_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_data_intake_requests_id'), 'data_intake_requests', ['id'], unique=False)
    op.create_index(op.f('ix_data_intake_requests_token'), 'data_intake_requests', ['token'], unique=True)

    # 3. Investee Submissions
    op.create_table(
        'investee_submissions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('contact_name', sa.String(), nullable=True),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('submitted_values', sa.JSON(), nullable=True),
        sa.Column('uploaded_file_name', sa.String(), nullable=True),
        sa.Column('uploaded_storage_url', sa.String(), nullable=True),
        sa.Column('file_hash', sa.String(), nullable=True),
        sa.Column('parsed_evidence', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='Received'),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['request_id'], ['data_intake_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_investee_submissions_id'), 'investee_submissions', ['id'], unique=False)

    # 4. Enterprise SSO Configs
    op.create_table(
        'enterprise_sso_configs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('protocol', sa.String(), nullable=True, server_default='SAML2'),
        sa.Column('idp_issuer', sa.String(), nullable=False),
        sa.Column('idp_sso_url', sa.String(), nullable=False),
        sa.Column('idp_certificate', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('auto_provision_users', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('default_role', sa.String(), nullable=True, server_default='Reviewer'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_enterprise_sso_configs_id'), 'enterprise_sso_configs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('enterprise_sso_configs')
    op.drop_table('investee_submissions')
    op.drop_table('data_intake_requests')
    op.drop_table('merkle_audit_checkpoints')
