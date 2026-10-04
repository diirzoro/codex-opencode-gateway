"""GitHub App connections/states, encrypted provider credentials, project remote metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0003_github_provider"
down_revision = "0002_workspaces"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("projects", sa.Column("github_repository_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("github_installation_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("remote_url", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("remote_branch", sa.String(120), nullable=True))

    op.create_table(
        "github_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_github_connection_user"),
        sa.UniqueConstraint("installation_id", name="uq_github_installation"),
    )
    op.create_table(
        "github_auth_states",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_github_auth_states_user_id", "github_auth_states", ["user_id"])
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("last4", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "provider_id", name="uq_provider_workspace"),
    )
    op.create_index("ix_provider_credentials_user_id", "provider_credentials", ["user_id"])
    op.create_index("ix_provider_credentials_workspace_id", "provider_credentials", ["workspace_id"])

def downgrade():
    op.drop_table("provider_credentials")
    op.drop_table("github_auth_states")
    op.drop_table("github_connections")
    op.drop_column("projects", "remote_branch")
    op.drop_column("projects", "remote_url")
    op.drop_column("projects", "github_installation_id")
    op.drop_column("projects", "github_repository_id")
