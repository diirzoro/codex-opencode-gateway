"""Persist actual admin-controlled email service policies; safe default is verification on."""
import sqlalchemy as sa
from alembic import op
revision = "0022_email_service_policies"
down_revision = "0021_email_delivery_settings"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("email_service_policies",
        sa.Column("service_id", sa.String(60), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
def downgrade():
    raise RuntimeError("Do not discard admin service policy preferences")
