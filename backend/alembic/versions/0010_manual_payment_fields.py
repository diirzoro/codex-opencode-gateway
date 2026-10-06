"""Manual-payment submission details shown on the customer form."""
from alembic import op
import sqlalchemy as sa
revision='0010_manual_payment_fields'
down_revision='0009_payment_receipts'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('payment_orders',sa.Column('billing_note',sa.String(500),nullable=True))
    op.add_column('payment_orders',sa.Column('sender_name',sa.String(150),nullable=True))
    op.add_column('payment_orders',sa.Column('transfer_date',sa.String(10),nullable=True))
    op.add_column('payment_orders',sa.Column('amount_sent_cents',sa.Integer(),nullable=True))
def downgrade():
    for name in ['amount_sent_cents','transfer_date','sender_name','billing_note']:op.drop_column('payment_orders',name)
