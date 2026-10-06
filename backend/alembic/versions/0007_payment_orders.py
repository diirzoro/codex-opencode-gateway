"""Manual payment review linked to subscription entitlement."""
from alembic import op
import sqlalchemy as sa
revision='0007_payment_orders'
down_revision='0006_subscriptions_archive'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('payment_orders',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),sa.Column('plan_id',sa.Integer(),sa.ForeignKey('plans.id'),nullable=False),sa.Column('method_id',sa.Uuid(),sa.ForeignKey('billing_methods.id',ondelete='SET NULL'),nullable=True),sa.Column('plan_name',sa.String(120),nullable=False),sa.Column('method_label',sa.String(100),nullable=False),sa.Column('amount_cents',sa.Integer(),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('duration_days',sa.Integer(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('payment_reference',sa.String(200)),sa.Column('confirmation_reference',sa.String(200)),sa.Column('reviewed_by',sa.Uuid(),sa.ForeignKey('users.id')),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('paid_at',sa.DateTime(timezone=True)))
    op.create_index('ix_payment_orders_user_id','payment_orders',['user_id'])
def downgrade():
    op.drop_table('payment_orders')
