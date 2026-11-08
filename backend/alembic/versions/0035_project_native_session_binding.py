"""Reserve one persistent OpenCode Native session binding per Project.

The legacy workspace_sessions history is deliberately untouched. Existing
projects are NOT auto-bound: projects with multiple legacy sessions require an
explicit, owner-reviewed selection and backup before activating this mapping.

This is Platform ownership metadata ONLY. Python must never query/create/patch
Native sessions while using this table. Browser -> Nginx -> OpenCode Native.
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_project_native_session_binding"
down_revision = "0034_profile_publications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_native_session_bindings",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("native_session_id", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "native_session_id", name="uq_project_native_binding_native_session"
        ),
    )


def downgrade():
    # Destructive: would remove administrative binding metadata, not Native history.
    # Never run on a populated environment without an owner-approved backup.
    op.drop_table("project_native_session_bindings")
