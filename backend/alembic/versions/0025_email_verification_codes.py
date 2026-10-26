"""Single-use bounded email codes; preserve all existing verification links and users."""
from alembic import op
import sqlalchemy as sa
revision='0025_email_verification_codes'
down_revision='0024_github_app_settings'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('email_verifications',sa.Column('verification_method',sa.String(8),nullable=False,server_default='link'))
    op.add_column('email_verifications',sa.Column('code_attempts',sa.Integer(),nullable=False,server_default='0'))


def downgrade():
    raise RuntimeError('Preserve verification attempts and pending registrations')
