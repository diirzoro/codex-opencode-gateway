#!/usr/bin/env bash
set -euo pipefail
[[ $(id -u) -eq 0 ]] || exit 1
exec /home/tahir/opencode-gateway/.venv/bin/python /home/tahir/preview-activation/scripts/preview-react-inspect.py
