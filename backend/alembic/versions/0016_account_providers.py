"""Account-level provider credentials.

Provider connection becomes an account-level concern: a signed-in user connects a
provider without first selecting a workspace. The credential store, encryption,
validation and discovery are unchanged; only the workspace_id scope becomes optional.
Account-level rows keep workspace_id NULL and are unique per (user, provider); the
existing workspace-scoped rows and their unique constraint are preserved.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_account_providers"
down_revision = "0015_homepage_content"
branch_labels = None
depends_on = None

ACCOUNT_INDEX = "uq_provider_account"


def upgrade():
    op.alter_column("provider_credentials", "workspace_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index(
        ACCOUNT_INDEX,
        "provider_credentials",
        ["user_id", "provider_id"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NULL"),
    )


def downgrade():
    op.drop_index(ACCOUNT_INDEX, table_name="provider_credentials")
    # Account-level rows cannot satisfy the restored NOT NULL column; they are
    # account-scoped additions, safe to remove on rollback.
    op.execute("DELETE FROM provider_credentials WHERE workspace_id IS NULL")
    op.alter_column("provider_credentials", "workspace_id", existing_type=sa.Uuid(), nullable=False)
