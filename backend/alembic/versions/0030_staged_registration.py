"""Unverified registration drafts: do not create User until email OTP verified.

Additive TEST migration. Does not change existing users or legacy pending_email rows.
"""
from alembic import op
import sqlalchemy as sa

revision='0030_staged_registration'
down_revision='0029_github_identity_registry'
branch_labels=depends_on=None

def upgrade():
    op.create_table('pending_registrations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('email_fingerprint',sa.String(64),nullable=False),
        sa.Column('ticket_hash',sa.String(64),nullable=False),
        sa.Column('payload_ciphertext',sa.Text(),nullable=False),
        sa.Column('code_hash',sa.String(64),nullable=False),
        sa.Column('code_expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_sent_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('sends',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_pending_registrations_email_fingerprint','pending_registrations',['email_fingerprint'])
    op.create_index('ix_pending_registrations_expires_at','pending_registrations',['expires_at'])

def downgrade():
    raise RuntimeError('Retain unverified signup drafts for reviewed rollback; do not drop signup data automatically')
