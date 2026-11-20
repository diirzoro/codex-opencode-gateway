"""Suspend new platform PayPal checkout by default, retain all paid records.

Admins may re-enable it later through the existing payment method controls.
This migration does not delete methods or change historical orders.
"""
from alembic import op
import sqlalchemy as sa

revision = "0042_suspend_paypal_platform_checkout"
down_revision = "0041_stripe_environment_credentials"
branch_labels = depends_on = None


def upgrade():
    op.execute(sa.text(
        "UPDATE billing_methods SET enabled = FALSE "
        "WHERE user_id IS NULL AND kind = 'paypal' AND enabled = TRUE"
    ))


def downgrade():
    # Never silently reactivate a payment provider during a rollback.
    pass
