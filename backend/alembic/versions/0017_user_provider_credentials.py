"""Introduce user-owned encrypted provider credentials without changing legacy bindings.

This expand-only migration intentionally does not copy workspace-owned records:
a user may have different secrets for the same provider in several workspaces.
Migration of those conflicts must be explicit, after an ownership audit.
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_user_provider_credentials"
down_revision = "0016_checkout_locations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_provider_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("last4", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "provider_id", name="uq_user_provider_credential"),
    )
    op.create_index("ix_user_provider_credentials_user_id", "user_provider_credentials", ["user_id"])


def downgrade():
    # Deliberately forbid dropping potentially irreplaceable encrypted secrets.
    raise RuntimeError("Destructive credential-table downgrade is forbidden; restore a reviewed backup instead.")
