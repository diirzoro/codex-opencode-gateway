"""Remove legacy Gateway copies of OpenCode provider secrets.

OpenCode Native is the only owner of API keys and OAuth credentials.
This is a deliberate destructive migration for the new TEST platform;
it does not modify the Native credential store, GitHub, email or billing.
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_native_only_provider_credentials"
down_revision = "0035_project_native_session_binding"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    # Both legacy tables contain ciphertext owned by Gateway, forbidden by
    # the current one-engine agreement. Do not copy or rehydrate their rows.
    for name in ("user_provider_credentials", "provider_credentials"):
        if name in existing:
            op.drop_table(name)


def downgrade():
    # Recreating a second credential store is prohibited by architecture.
    raise RuntimeError("Gateway OpenCode credential tables must not be recreated")
