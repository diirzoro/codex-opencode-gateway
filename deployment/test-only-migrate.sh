#!/usr/bin/env bash
# TEST-only privileged launcher. Install root-owned via documented sudoers rule.
# systemd (not a root shell) parses protected EnvironmentFile values.
set -euo pipefail
[[ "${1:-}" == "upgrade" ]] || { echo "Usage: $0 upgrade" >&2; exit 64; }
APP=/home/tahir/opencode-gateway-test
ENV1="$APP/state/rollback-80275b121918462c920af81e6fde2145/runtime.env"
ENV2=/etc/opencode-gateway-test/native-release.env
[[ -f "$ENV1" && -f "$ENV2" ]] || { echo "Required protected TEST environment not found" >&2; exit 1; }
run_test_python() {
  systemd-run --quiet --wait --collect --pipe \
    --property=Type=exec \
    --property=User=tahir \
    --property=WorkingDirectory="$APP/backend" \
    --property=EnvironmentFile="$ENV1" \
    --property=EnvironmentFile="$ENV2" \
    "$APP/.venv/bin/python" "$@"
}
run_test_python -c 'from app.database import engine; from sqlalchemy import text; connection=engine.connect(); name=connection.scalar(text("select current_database()")); connection.close(); assert name=="opencode_gateway_test", "Wrong database"; print("TEST_DATABASE_CONFIRMED")'
run_test_python -m alembic upgrade head
run_test_python -m alembic current
echo TEST_DB_MIGRATION_OK
