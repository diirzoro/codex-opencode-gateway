#!/usr/bin/env bash
set -euo pipefail
: "${APP_HOST:?APP_HOST is required}"
: "${APP_PORT:?APP_PORT is required}"
BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$(cd -- "$BACKEND_DIR/.." && pwd)/.venv"
exec "$VENV_DIR/bin/uvicorn" app.main:app --host "$APP_HOST" --port "$APP_PORT" --proxy-headers --forwarded-allow-ips=127.0.0.1
