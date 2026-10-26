"""Deduplicate real Gateway notification events without storing message content."""
from alembic import op
import sqlalchemy as sa
revision='0027_email_notification_receipts'
down_revision='0026_unique_registration_identities'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('email_notification_receipts',sa.Column('event_key',sa.String(220),primary_key=True),sa.Column('source_key',sa.String(220),nullable=False,index=True),sa.Column('service_id',sa.String(50),nullable=False),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),sa.Column('state',sa.String(20),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))

def downgrade():
    raise RuntimeError('Preserve notification deduplication history')
