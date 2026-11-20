"""Store Arabic and English plan descriptions."""

from alembic import op
import sqlalchemy as sa

revision = "0044_plan_descriptions"
down_revision = "0043_plan_storage"
branch_labels = depends_on = None


def upgrade():
    op.add_column("plans", sa.Column("description_ar", sa.Text(), nullable=False, server_default=""))
    op.add_column("plans", sa.Column("description_en", sa.Text(), nullable=False, server_default=""))
    op.execute(sa.text(
        "UPDATE plans SET description_ar = :ar, description_en = :en"
    ).bindparams(
        ar="المشاريع المحلية وGitHub معًا · حصة واحدة للحساب",
        en="Local and GitHub combined · one account quota",
    ))


def downgrade():
    op.drop_column("plans", "description_en")
    op.drop_column("plans", "description_ar")
