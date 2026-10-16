"""Add durable Preview lease records without enabling preview code execution."""
from alembic import op
import sqlalchemy as sa

revision = "0019_preview_runtime_leases"
down_revision = "0018_email_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "preview_runtime_leases",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column("pool_id", sa.String(length=120), nullable=True),
        sa.Column("source_revision", sa.String(length=128), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("last_user_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("state IN ('queued','starting','running','stopped','failed','expired')", name="ck_preview_lease_state"),
        sa.UniqueConstraint("workspace_id", name="uq_preview_lease_workspace"),
    )
    op.create_index("ix_preview_runtime_leases_workspace_id", "preview_runtime_leases", ["workspace_id"], unique=False)
    op.create_index("ix_preview_runtime_leases_user_id", "preview_runtime_leases", ["user_id"], unique=False)
    op.create_index("ix_preview_lease_state_seen", "preview_runtime_leases", ["state", "last_user_activity_at"], unique=False)


def downgrade():
    op.drop_index("ix_preview_lease_state_seen", table_name="preview_runtime_leases")
    op.drop_index("ix_preview_runtime_leases_user_id", table_name="preview_runtime_leases")
    op.drop_index("ix_preview_runtime_leases_workspace_id", table_name="preview_runtime_leases")
    op.drop_table("preview_runtime_leases")
