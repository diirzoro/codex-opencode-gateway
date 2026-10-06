"""Plan catalog, user plan assignment and platform provider/model/tool policy."""
from alembic import op
import sqlalchemy as sa

revision = "0004_plans_policy"
down_revision = "0003_github_provider"
branch_labels = None
depends_on = None

plans_table = sa.table(
    "plans",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("price_cents", sa.Integer),
    sa.column("currency", sa.String),
    sa.column("duration_days", sa.Integer),
    sa.column("active", sa.Boolean),
    sa.column("sort_order", sa.Integer),
)

def upgrade():
    plans = op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(plans, [
        {"code": "monthly", "name": "1 month", "price_cents": 200, "currency": "USD", "duration_days": 30, "active": True, "sort_order": 1},
        {"code": "two_months", "name": "2 months", "price_cents": 300, "currency": "USD", "duration_days": 60, "active": True, "sort_order": 2},
        {"code": "three_months", "name": "3 months", "price_cents": 500, "currency": "USD", "duration_days": 90, "active": True, "sort_order": 3},
    ])
    op.create_table(
        "platform_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allowed_providers", sa.Text(), nullable=False),
        sa.Column("allowed_models", sa.Text(), nullable=False),
        sa.Column("allowed_tools", sa.Text(), nullable=False),
        sa.Column("require_tool_approval", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "INSERT INTO platform_policy (id, allowed_providers, allowed_models, allowed_tools, require_tool_approval) "
        "VALUES (1, '[]', '[]', '[]', TRUE)"
    )
    op.add_column("users", sa.Column("plan_id", sa.Integer(), nullable=True))
    # SQLite cannot add a foreign-key constraint through ALTER; enforce via the ORM there.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_users_plan_id", "users", "plans", ["plan_id"], ["id"])

def downgrade():
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_users_plan_id", "users", type_="foreignkey")
    op.drop_column("users", "plan_id")
    op.drop_table("platform_policy")
    op.drop_table("plans")
