"""Owned local projects, workspaces, sessions and ordered execution metadata."""
from alembic import op
import sqlalchemy as sa
revision = "0002_workspaces"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("projects", sa.Column("id",sa.Uuid(),primary_key=True), sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False), sa.Column("name",sa.String(120),nullable=False), sa.Column("source_type",sa.String(20),nullable=False), sa.Column("repository",sa.String(255)), sa.Column("default_branch",sa.String(120),nullable=False), sa.Column("template",sa.String(40)), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.CheckConstraint("source_type IN ('github','blank','template')",name="ck_project_source"))
    op.create_index("ix_projects_user_id","projects",["user_id"])
    op.create_table("workspaces",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("project_id",sa.Uuid(),sa.ForeignKey("projects.id"),nullable=False),sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("base_commit_sha",sa.String(64)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("last_activity_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_workspaces_user_id","workspaces",["user_id"])
    op.create_index("ix_workspaces_project_id","workspaces",["project_id"])
    op.create_table("workspace_sessions",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("workspace_id",sa.Uuid(),sa.ForeignKey("workspaces.id"),nullable=False),sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False),sa.Column("opencode_session_id",sa.String(120),nullable=False),sa.Column("title",sa.String(120),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_workspace_sessions_user_id","workspace_sessions",["user_id"])
    op.create_index("ix_workspace_sessions_workspace_id","workspace_sessions",["workspace_id"])
    op.create_table("execution_events",sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),sa.Column("session_id",sa.Uuid(),sa.ForeignKey("workspace_sessions.id"),nullable=False),sa.Column("kind",sa.String(50),nullable=False),sa.Column("data",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_execution_events_session_id","execution_events",["session_id"])

def downgrade():
    for name in ("execution_events","workspace_sessions","workspaces","projects"):
        op.drop_table(name)
