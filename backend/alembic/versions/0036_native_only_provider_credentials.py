"""Retire Gateway-owned OpenCode credential tables without requiring DDL ownership.

OpenCode Native alone owns AI provider keys, OAuth and authentication.
Gateway models and services have been removed independently of these old tables.

TEST's migration role may have SELECT but not DROP ownership on historical
PostgreSQL tables. Never weaken the deployment migration gate or elevate the
database role; verify that every inaccessible-for-DDL legacy table is EMPTY.
An empty orphan table is harmless but must be removed by its owner separately.
If any old credential row remains, fail closed rather than silently abandoning
a copy of a secret in Gateway PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_native_only_provider_credentials"
down_revision = "0035_project_native_session_binding"
branch_labels = None
depends_on = None

LEGACY_TABLES = ("user_provider_credentials", "provider_credentials")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in LEGACY_TABLES:
        if name not in existing:
            continue
        # Check whether the migration role can act as this table's owner.
        # pg_has_role is catalog-only; it doesn't disclose table contents.
        can_drop = bind.execute(sa.text("""
            SELECT pg_has_role(current_user, c.relowner, 'USAGE')
            FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema()
              AND c.relname = :name
              AND c.relkind IN ('r', 'p')
        """), {"name": name}).scalar()
        if can_drop:
            op.drop_table(name)
            continue

        # We must not represent a table containing API keys as eliminated.
        # These names are fixed constants, never user-provided SQL identifiers.
        count = bind.execute(sa.text(
            'SELECT count(*) FROM "' + name + '"'
        )).scalar_one()
        if count:
            raise RuntimeError(
                "Legacy Gateway AI credential table still contains rows: "
                + name + ". Table owner must securely purge it before TEST deploy."
            )

        # Existing zero-row tables are inert. No INSERT/UPDATE/SELECT routes,
        # ORM models or credential services remain in the Gateway application.
        # Drop requires the table owner; do not change passwords, owners or grants.
        print("LEGACY_GATEWAY_CREDENTIAL_TABLE_EMPTY_OWNER_CLEANUP_REQUIRED", name)


def downgrade():
    raise RuntimeError(
        "Gateway AI credential models and tables must not be recreated"
    )
