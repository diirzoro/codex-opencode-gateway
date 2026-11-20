"""Keep TEST and LIVE Stripe credentials separately while changing the active mode.

Existing merchant profile remains authoritative for active mode. Old values are
migrated lazily when the profile is edited or used; no credentials are logged.
"""
from alembic import op
import sqlalchemy as sa

revision = "0041_stripe_environment_credentials"
down_revision = "0040_payment_provider_verification"
branch_labels = depends_on = None

def upgrade():
    op.create_table(
        "stripe_environment_credentials",
        sa.Column("environment", sa.String(10), primary_key=True),
        sa.Column("encrypted_fields", sa.Text(), nullable=False),
        sa.Column("verification_fingerprint", sa.String(64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_account_id", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("environment IN ('test','live')", name="ck_stripe_environment"),
    )

def downgrade():
    op.drop_table("stripe_environment_credentials")
