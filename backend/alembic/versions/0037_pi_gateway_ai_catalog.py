"""Install the Pi Gateway provider catalog and per-account credentials schema.

0036 retired the historical OpenCode credential tables. The Pi catalog tables
were documented as manual TEST-only SQL, so LIVE reached 0036 without them.

This migration works independently in the existing TEST and LIVE databases:
- New database: create all three tables and their indexes transactionally.
- Existing TEST manual installation: verify its shape, then register 0037.
- Partial or incompatible installations: fail closed, never drop or overwrite.

No provider keys, payment, email, account or workspace rows are migrated.
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_pi_gateway_ai_catalog"
down_revision = "0036_native_only_provider_credentials"
branch_labels = None
depends_on = None

TABLES = (
    "ai_provider_catalog",
    "ai_provider_models",
    "ai_user_connections",
)
REQUIRED_COLUMNS = {
    "ai_provider_catalog": {
        "id", "name", "model_count", "models_synced_at",
        "last_sync_error", "updated_at",
    },
    "ai_provider_models": {
        "provider_id", "model_id", "name", "details_json",
        "active", "updated_at",
    },
    "ai_user_connections": {
        "id", "user_id", "provider_id", "ciphertext",
        "last4", "auth_status", "credit_status", "verified_at",
        "updated_at",
    },
}
PRIMARY_KEYS = {
    "ai_provider_catalog": {"id"},
    "ai_provider_models": {"provider_id", "model_id"},
    "ai_user_connections": {"id"},
}


def _validate_existing(bind):
    """Do not accept a drifted, partially installed manual schema as current."""
    inspector = sa.inspect(bind)
    for name in TABLES:
        fields = {column["name"] for column in inspector.get_columns(name)}
        missing = REQUIRED_COLUMNS[name] - fields
        if missing:
            raise RuntimeError(
                "Existing Pi catalog table has missing columns: "
                + name + " (" + ", ".join(sorted(missing)) + ")"
            )
        pk = set(inspector.get_pk_constraint(name).get("constrained_columns") or ())
        if pk != PRIMARY_KEYS[name]:
            raise RuntimeError("Existing Pi catalog table has incompatible primary key: " + name)

    unique = inspector.get_unique_constraints("ai_user_connections")
    matching_unique = any(
        set(item.get("column_names") or ()) == {"user_id", "provider_id"}
        for item in unique
    )
    if not matching_unique:
        raise RuntimeError("Existing Pi connections table lacks unique (user_id, provider_id)")

    expected_fks = {
        "ai_provider_models": {
            ("provider_id", "ai_provider_catalog", "id"),
        },
        "ai_user_connections": {
            ("user_id", "users", "id"),
            ("provider_id", "ai_provider_catalog", "id"),
        },
    }
    for table, expected in expected_fks.items():
        found = set()
        for fk in inspector.get_foreign_keys(table):
            local = fk.get("constrained_columns") or ()
            remote = fk.get("referred_columns") or ()
            if len(local) == 1 and len(remote) == 1:
                found.add((local[0], fk.get("referred_table"), remote[0]))
        if not expected.issubset(found):
            raise RuntimeError("Existing Pi catalog table lacks required foreign keys: " + table)

    for table, required_index in (
        ("ai_provider_models", "ix_ai_provider_models_name"),
        ("ai_user_connections", "ix_ai_user_connections_user_id"),
    ):
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        if required_index not in indexes:
            raise RuntimeError(
                "Existing Pi catalog table lacks required index: " + required_index
            )


def upgrade():
    bind = op.get_bind()
    db_name = bind.execute(sa.text("SELECT current_database()")).scalar_one()
    if db_name not in {"opencode_gateway", "opencode_gateway_test"}:
        raise RuntimeError("Refusing Pi catalog migration outside the existing LIVE/TEST database")

    existing = set(sa.inspect(bind).get_table_names())
    present = set(TABLES) & existing
    if present:
        if present != set(TABLES):
            raise RuntimeError(
                "Partial Pi catalog schema detected; refusing automatic repair: "
                + ", ".join(sorted(present))
            )
        _validate_existing(bind)
        return

    op.create_table(
        "ai_provider_catalog",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("model_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("models_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_error", sa.String(120)),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ai_provider_models",
        sa.Column("provider_id", sa.String(120),
                  sa.ForeignKey("ai_provider_catalog.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("model_id", sa.String(300), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("provider_id", "model_id",
                                name="pk_ai_provider_models"),
    )
    # Match the established TEST manual SQL index and keep model search fast.
    op.execute(
        "CREATE INDEX ix_ai_provider_models_name "
        "ON ai_provider_models (provider_id, lower(name))"
    )

    op.create_table(
        "ai_user_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider_id", sa.String(120),
                  sa.ForeignKey("ai_provider_catalog.id"),
                  nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("auth_status", sa.String(40),
                  nullable=False, server_default="verified"),
        sa.Column("credit_status", sa.String(40),
                  nullable=False, server_default="unknown"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "provider_id", name="uq_ai_user_provider"),
    )
    op.create_index(
        "ix_ai_user_connections_user_id",
        "ai_user_connections",
        ["user_id"],
    )


def downgrade():
    # Never destroy account-owned encrypted API keys or provider metadata.
    raise RuntimeError("Pi catalog migration is non-destructive and cannot be downgraded")
