"""Encrypted admin mailbox drafts; no plaintext message contents persisted."""
import sqlalchemy as sa
from alembic import op
revision = "0023_admin_mail_drafts"
down_revision = "0022_email_service_policies"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "admin_mail_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("admin_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_mail_drafts_admin_updated", "admin_mail_drafts", ["admin_id", "updated_at"])

def downgrade():
    raise RuntimeError("Do not discard saved admin email drafts")
