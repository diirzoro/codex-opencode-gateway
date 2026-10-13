"""Add verification token storage without changing existing accounts.

Existing users retain status and trial balances. New unverified customers use
status=pending_email until they prove email ownership.
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_email_verification"
down_revision = "0017_user_provider_credentials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"])
    op.create_index("ix_email_verifications_token_hash", "email_verifications", ["token_hash"], unique=True)


def downgrade():
    raise RuntimeError("Do not destructively downgrade account verification records")
