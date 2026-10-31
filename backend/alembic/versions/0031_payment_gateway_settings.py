"""Encrypted admin settings for Stripe and Cryptomus, configuration only.

No payment initiation, subscription activation, webhook processing or payouts.
"""
import sqlalchemy as sa
from alembic import op

revision = "0031_payment_gateway_settings"
down_revision = "0030_staged_registration"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "payment_gateway_settings",
        sa.Column("provider", sa.String(24), primary_key=True),
        sa.Column("encrypted_data", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('stripe', 'cryptomus')",
                           name="ck_payment_gateway_provider"),
    )


def downgrade():
    raise RuntimeError("Do not discard encrypted payment provider credentials")
