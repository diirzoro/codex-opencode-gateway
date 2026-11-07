"""Add private verified GitHub identity history; preserve all existing data."""
from alembic import op
import sqlalchemy as sa

revision = '0029_github_identity_registry'
down_revision = '0028_github_connection_identity'
branch_labels = depends_on = None


def upgrade():
    # No inferred backfill: existing connection rows do not prove a current
    # primary-email HMAC. Entries are created only after fresh email+OTP proof.
    op.create_table('github_identity_registry',
        sa.Column('github_user_id', sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column('primary_email_hmac', sa.String(64), nullable=False),
        sa.Column('first_verified_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('retain_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verification_status', sa.String(30), nullable=False, server_default='verified'),
        sa.CheckConstraint('github_user_id > 0', name='ck_github_registry_positive_id'))
    op.create_index('ix_github_identity_registry_last_verified_at', 'github_identity_registry', ['last_verified_at'])
    op.create_index('ix_github_identity_registry_retain_until', 'github_identity_registry', ['retain_until'])


def downgrade():
    raise RuntimeError('Preserve verified GitHub history; use a reviewed, non-destructive application rollback')
