"""Persist administrator suspension independently from checkout publication."""
from alembic import op
import sqlalchemy as sa

revision = '0039_payment_profile_suspension'
down_revision = '0038_admin_finance_crud'
branch_labels = depends_on = None

def upgrade():
    op.add_column('payment_provider_profiles', sa.Column('admin_suspended', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('payment_provider_profiles', 'admin_suspended')
