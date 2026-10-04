"""Account recovery, encrypted payment details and account audit."""
from alembic import op
import sqlalchemy as sa
revision='0005_account_management'
down_revision='0004_plans_policy'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('github_connections',sa.Column('user_token',sa.Text(),nullable=True))
    op.add_column('github_connections',sa.Column('token_expires_at',sa.DateTime(timezone=True),nullable=True))
    op.create_table('billing_methods',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=True),sa.Column('kind',sa.String(20),nullable=False),sa.Column('label',sa.String(100),nullable=False),sa.Column('details',sa.Text(),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False))
    op.create_index('ix_billing_methods_user_id','billing_methods',['user_id'])
    op.create_table('account_audit',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id')),sa.Column('subject_id',sa.Uuid(),sa.ForeignKey('users.id')),sa.Column('action',sa.String(80),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_account_audit_subject_id','account_audit',['subject_id'])
    op.create_table('password_resets',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),sa.Column('token_hash',sa.String(64),unique=True,nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('used',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_password_resets_user_id','password_resets',['user_id'])

def downgrade():
    op.drop_column('github_connections','token_expires_at')
    op.drop_column('github_connections','user_token')
    for name in ['password_resets','account_audit','billing_methods']: op.drop_table(name)
