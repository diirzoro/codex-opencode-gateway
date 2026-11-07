"""Encrypted platform GitHub App settings; preserve all customer connections."""
import sqlalchemy as sa
from alembic import op
revision='0024_github_app_settings'
down_revision='0023_admin_mail_drafts'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('github_app_settings',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('encrypted_data',sa.Text(),nullable=False),
        sa.Column('updated_by',sa.Uuid(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))

def downgrade():
    raise RuntimeError('Do not discard encrypted GitHub App configuration')
