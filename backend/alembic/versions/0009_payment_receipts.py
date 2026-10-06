"""Manual-payment receipt evidence and review outcome."""
from alembic import op
import sqlalchemy as sa
revision='0009_payment_receipts'
down_revision='0008_paypal_checkout'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('payment_orders',sa.Column('receipt_path',sa.String(500),nullable=True))
    op.add_column('payment_orders',sa.Column('reject_reason',sa.String(500),nullable=True))
def downgrade():
    for name in ['reject_reason','receipt_path']:op.drop_column('payment_orders',name)
