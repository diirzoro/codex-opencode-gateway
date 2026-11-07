"""Add encrypted, admin-configurable payment/bank provider profiles.

These are configuration drafts only. Existing BillingMethod, PayPal, Stripe and
Cryptomus configuration, payment orders and production settings are untouched.
"""
import sqlalchemy as sa
from alembic import op

revision = "0033_payment_profiles"
down_revision = "0032_unified_storage_plans"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "payment_provider_profiles",
        sa.Column("slug", sa.String(60), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("connection_mode", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False, server_default="test"),
        sa.Column("encrypted_fields", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("category IN ('bank','wallet','processor','crypto','other')",
                           name="ck_payment_profile_category"),
        sa.CheckConstraint("connection_mode IN ('manual','hosted','api')",
                           name="ck_payment_profile_connection_mode"),
        sa.CheckConstraint("environment IN ('test','live')",
                           name="ck_payment_profile_environment"),
    )


def downgrade():
    raise RuntimeError("Do not delete encrypted payment provider profiles or merchant settings")
