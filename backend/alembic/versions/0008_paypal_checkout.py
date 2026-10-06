"""Persist verified PayPal order and capture identity."""
from alembic import op
import sqlalchemy as sa
revision='0008_paypal_checkout'
down_revision='0007_payment_orders'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('payment_orders',sa.Column('provider_order_id',sa.String(100),nullable=True))
    op.add_column('payment_orders',sa.Column('provider_capture_id',sa.String(100),nullable=True))
    op.add_column('payment_orders',sa.Column('provider_environment',sa.String(10),nullable=True))
    op.create_index('uq_payment_provider_order','payment_orders',['provider_order_id'],unique=True)
    op.create_index('uq_payment_provider_capture','payment_orders',['provider_capture_id'],unique=True)
def downgrade():
    op.drop_index('uq_payment_provider_capture',table_name='payment_orders')
    op.drop_index('uq_payment_provider_order',table_name='payment_orders')
    for name in ['provider_environment','provider_capture_id','provider_order_id']:op.drop_column('payment_orders',name)
