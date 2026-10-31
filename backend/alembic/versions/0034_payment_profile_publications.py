"""Opt-in mapping from a dynamic provider to an existing verified-receipt checkout method.

No real gateway charge, payout or webhook is created. Historical payment
orders retain their method ID and are never deleted on unpublication.
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_payment_profile_publications"
down_revision = "0033_payment_profiles"
branch_labels = depends_on = None

def upgrade():
    op.create_table(
        "payment_profile_publications",
        sa.Column("profile_slug",sa.String(60),sa.ForeignKey("payment_provider_profiles.slug"),primary_key=True),
        sa.Column("method_id",sa.Uuid(),sa.ForeignKey("billing_methods.id"),unique=True,nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
    )

def downgrade():
    raise RuntimeError("Preserve historical checkout method references and publication settings")
