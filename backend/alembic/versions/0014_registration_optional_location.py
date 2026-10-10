"""Make country and postal code optional for new registrations.

Country, region, city and postal code are no longer collected at signup;
they are completed later from Account/Profile. Existing values are preserved.
"""
from alembic import op
import sqlalchemy as sa
revision = "0014_optional_location"
down_revision = "0013_login_identity"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("users", "country_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("users", "postal_code", existing_type=sa.String(24), nullable=True)

def downgrade():
    # Backfill before restoring NOT NULL so existing simplified accounts stay valid.
    op.execute("UPDATE users SET postal_code = '' WHERE postal_code IS NULL")
    op.execute("UPDATE users SET country_id = (SELECT id FROM countries ORDER BY id LIMIT 1) WHERE country_id IS NULL")
    op.alter_column("users", "postal_code", existing_type=sa.String(24), nullable=False)
    op.alter_column("users", "country_id", existing_type=sa.Integer(), nullable=False)
