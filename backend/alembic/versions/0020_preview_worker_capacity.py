"""Create trusted Preview worker capacity registry; no workers enabled."""
from alembic import op
import sqlalchemy as sa

revision = "0020_preview_worker_capacity"
down_revision = "0019_preview_runtime_leases"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "preview_worker_capacities",
        sa.Column("worker_id", sa.String(120), primary_key=True),
        sa.Column("isolated", sa.Boolean(), nullable=False),
        sa.Column("security_verified", sa.Boolean(), nullable=False),
        sa.Column("reachable", sa.Boolean(), nullable=False),
        sa.Column("cpu_free_millicores", sa.Integer(), nullable=False),
        sa.Column("memory_free_mb", sa.Integer(), nullable=False),
        sa.Column("disk_free_mb", sa.Integer(), nullable=False),
        sa.Column("active_jobs", sa.Integer(), nullable=False),
        sa.Column("max_jobs", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("isolation_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("active_jobs >= 0 AND max_jobs >= 0 AND active_jobs <= max_jobs", name="ck_preview_worker_slots"),
        sa.CheckConstraint("cpu_free_millicores >= 0 AND memory_free_mb >= 0 AND disk_free_mb >= 0", name="ck_preview_worker_resources"),
    )

def downgrade():
    op.drop_table("preview_worker_capacities")
