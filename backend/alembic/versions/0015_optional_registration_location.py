"""Allow registration without geographic fields; preserve existing user locations."""
from alembic import op
import sqlalchemy as sa
revision = "0015_optional_registration_location"
down_revision = "0014_homepage_content"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("users", "country_id", existing_type=sa.Integer(), nullable=True)

def downgrade():
    # Do not assign an invented location to accounts created without a country.
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM users WHERE country_id IS NULL")):
        raise RuntimeError("Set countries for users with no country before downgrading")
    op.alter_column("users", "country_id", existing_type=sa.Integer(), nullable=False)
