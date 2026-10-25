#!/usr/bin/env bash
# Root-installed, TEST-only database migration runner. Do not use for LIVE.
set -euo pipefail
[[ "${1:-}" == "upgrade" ]] || { echo "Usage: $0 upgrade" >&2; exit 64; }
APP=/home/tahir/opencode-gateway-test
cd "$APP/backend"
set -a
source "$APP/state/rollback-80275b121918462c920af81e6fde2145/runtime.env"
source /etc/opencode-gateway-test/native-release.env
set +a
# Verify target by querying the actual database, not by trusting the URL.
"$APP/.venv/bin/python" - <<'PY'
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    database = conn.scalar(text("select current_database()"))
if database != "opencode_gateway_test":
    raise SystemExit("Refusing migrations: database is not opencode_gateway_test")
print("TEST_DATABASE_CONFIRMED", flush=True)
PY
"$APP/.venv/bin/python" -m alembic upgrade head
"$APP/.venv/bin/python" -m alembic current
echo TEST_DB_MIGRATION_OK
