"""Add admin-side notes and saved report definitions; do not mutate financial ledgers.

Existing payment orders, subscriptions, methods, and their audit history are
unchanged. This is additive and safe for isolated LIVE/TEST databases.
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_admin_finance_crud"
down_revision = "0037_pi_gateway_ai_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("subscriptions", sa.Column("admin_suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "admin_finance_notes",
        sa.Column("target_type", sa.String(16), primary_key=True),
        sa.Column("target_id", sa.String(36), primary_key=True),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "admin_report_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_column("subscriptions", "admin_suspended_at")
    op.drop_table("admin_report_presets")
    op.drop_table("admin_finance_notes")
