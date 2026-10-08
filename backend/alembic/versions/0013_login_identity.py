"""Bind verified social identities to existing Gateway users."""
from alembic import op
import sqlalchemy as sa
revision = "0013_login_identity"
down_revision = "0012_advanced_trial"
branch_labels = None
depends_on = None

def upgrade():
    for provider, length in (("github", 100), ("google", 255)):
        name = provider + "_subject"
        op.add_column("users", sa.Column(name, sa.String(length), nullable=True))
        op.create_unique_constraint("uq_users_" + name, "users", [name])

def downgrade():
    for provider in ("google", "github"):
        name = provider + "_subject"
        op.drop_constraint("uq_users_" + name, "users", type_="unique")
        op.drop_column("users", name)
