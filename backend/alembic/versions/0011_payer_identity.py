"""Customer-entered payment identity on every payment."""
from alembic import op
import sqlalchemy as sa
revision='0011_payer_identity'
down_revision='0010_manual_payment_fields'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('payment_orders',sa.Column('sender_email',sa.String(254),nullable=True))
    op.add_column('payment_orders',sa.Column('sender_bank',sa.String(150),nullable=True))
    op.add_column('payment_orders',sa.Column('sender_account',sa.String(200),nullable=True))
    op.add_column('payment_orders',sa.Column('payer_name',sa.String(150),nullable=True))
    op.add_column('payment_orders',sa.Column('payer_email',sa.String(254),nullable=True))
    op.add_column('payment_orders',sa.Column('payer_country',sa.String(80),nullable=True))
def downgrade():
    for name in ['payer_country','payer_email','payer_name','sender_account','sender_bank','sender_email']:op.drop_column('payment_orders',name)
