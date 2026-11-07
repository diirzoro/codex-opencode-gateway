"""Three unified Gateway storage tiers; preserves prior plan rows and paid periods.

A single subscription pays for Gateway service and shared local/GitHub disk quota.
AI API tokens, credentials and model usage are customer-supplied (BYOK).
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_unified_storage_plans"
down_revision = "0031_payment_gateway_settings"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    plans = sa.table(
        "plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("price_cents", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("duration_days", sa.Integer),
        sa.column("active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    # No rewriting of existing Subscription, PaymentOrder, customer or invoice.
    # Existing purchased terms remain valid at their recorded duration and price.
    existing = set(connection.execute(sa.text("SELECT code FROM plans")).scalars())
    for code, name, cents, amount, rank in (
        ("gateway_100", "Gateway Basic — 100 MB", 200, 100, 10),
        ("gateway_150", "Gateway Standard — 150 MB", 300, 150, 20),
        ("gateway_250", "Gateway Plus — 250 MB", 500, 250, 30),
    ):
        if code not in existing:
            connection.execute(plans.insert().values(
                code=code, name=name, price_cents=cents, currency="USD",
                duration_days=30, active=True, sort_order=rank,
            ))
    # Retire ONLY uncustomized default legacy sale offers.
    # Subscribers with legacy plans keep their existing purchased terms.
    for code, cents, days in (
        ("monthly", 200, 30),
        ("two_months", 300, 60),
        ("three_months", 500, 90),
    ):
        connection.execute(sa.text(
            "UPDATE plans SET active = false WHERE code = :code "
            "AND price_cents = :cents AND duration_days = :days"
        ), {"code": code, "cents": cents, "days": days})


def downgrade():
    raise RuntimeError("Unified plan rollout is forward-only; preserve purchased plans")
