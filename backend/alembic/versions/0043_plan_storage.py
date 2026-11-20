"""Persist the storage allowance for each Gateway plan."""

from alembic import op
import sqlalchemy as sa

revision = "0043_plan_storage"
down_revision = "0042_suspend_paypal_platform_checkout"
branch_labels = depends_on = None


def upgrade():
    op.add_column("plans", sa.Column("storage_mb", sa.Integer(), server_default="50", nullable=False))
    op.execute(sa.text("""
        UPDATE plans SET storage_mb = CASE
            WHEN code IN ('gateway_100', 'monthly') THEN 100
            WHEN code IN ('gateway_150', 'two_months') THEN 150
            WHEN code IN ('gateway_250', 'three_months') THEN 250
            ELSE 50 END
    """))


def downgrade():
    op.drop_column("plans", "storage_mb")
