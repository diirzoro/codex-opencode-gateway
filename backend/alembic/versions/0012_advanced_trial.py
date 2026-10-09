"""Separate first-use advanced trial without replacing existing account trials."""
from alembic import op
import sqlalchemy as sa

revision = "0012_advanced_trial"
down_revision = "0011_payer_identity"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("advanced_trial_started_at", sa.DateTime(timezone=True), nullable=True))
    # Conservatively preserve any account touched by admin controls, and every
    # non-default deadline. Never restart a trial from migration/deployment time.
    op.execute("""
        UPDATE users u SET trial_ends_at = trial_started_at + INTERVAL '30 days'
        WHERE trial_ends_at = trial_started_at + INTERVAL '10 days'
          AND NOT EXISTS (SELECT 1 FROM account_audit a WHERE a.subject_id = u.id
                          AND a.action = 'account.admin_updated')
    """)
    # Existing saved connections are evidence of real prior advanced use.
    op.execute("""
        UPDATE users u SET advanced_trial_started_at = first_use.started
        FROM (SELECT user_id, MIN(created_at) AS started FROM (
            SELECT user_id, created_at FROM provider_credentials
            UNION ALL SELECT user_id, created_at FROM github_connections
            UNION ALL SELECT subject_id AS user_id, created_at FROM account_audit
                      WHERE action LIKE 'provider-on:%' AND subject_id IS NOT NULL
        ) connections GROUP BY user_id) first_use
        WHERE u.id = first_use.user_id
    """)

def downgrade():
    # Do not shorten existing/admin trial deadlines when rolling back schema.
    op.drop_column("users", "advanced_trial_started_at")
