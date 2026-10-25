"""Protected admin-selected SMTP provider configuration."""
import sqlalchemy as sa
from alembic import op
revision="0021_email_delivery_settings"
down_revision="0020_preview_worker_capacity"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("email_delivery_settings",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("encrypted_data",sa.Text(),nullable=False),
        sa.Column("updated_by",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
def downgrade():
    raise RuntimeError("Do not discard encrypted email delivery configuration")
