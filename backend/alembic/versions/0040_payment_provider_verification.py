"""Remember successful provider API checks for exactly the saved credential revision.

This stores no API keys, payment rights, or customer checkout state.
"""
from alembic import op
import sqlalchemy as sa

revision = "0040_payment_provider_verification"
down_revision = "0039_payment_profile_suspension"
branch_labels = depends_on = None


def upgrade():
    op.add_column("payment_provider_profiles", sa.Column("verification_fingerprint", sa.String(64), nullable=True))
    op.add_column("payment_provider_profiles", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_provider_profiles", sa.Column("verified_account_id", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("payment_provider_profiles", "verified_account_id")
    op.drop_column("payment_provider_profiles", "verified_at")
    op.drop_column("payment_provider_profiles", "verification_fingerprint")
