"""Add session-bound GitHub confirmation; preserve existing connections and files."""
from alembic import op
import sqlalchemy as sa
revision = '0028_github_connection_identity'
down_revision = '0027_email_notification_receipts'
branch_labels = depends_on = None

def upgrade():
    op.add_column('github_connections', sa.Column('github_user_id', sa.BigInteger(), nullable=True))
    op.add_column('github_connections', sa.Column('github_user_login', sa.String(120), nullable=True))
    op.create_index('ix_github_connections_github_user_id', 'github_connections', ['github_user_id'], unique=True)
    op.add_column('github_auth_states', sa.Column('auth_session_id', sa.Uuid(), nullable=True))
    op.add_column('github_auth_states', sa.Column('connection_id', sa.Uuid(), nullable=True))
    op.add_column('github_auth_states', sa.Column('pending_payload', sa.Text(), nullable=True))
    op.create_foreign_key('fk_github_state_auth_session', 'github_auth_states', 'auth_sessions', ['auth_session_id'], ['id'], ondelete='SET NULL')

def downgrade():
    raise RuntimeError('Preserve GitHub identity and pending authorization records; use a reviewed rollback')
