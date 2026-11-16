#!/usr/bin/env bash
set -euo pipefail
[[ $(id -u) -eq 0 ]] || exit 1
exec python3 /home/tahir/preview-activation/scripts/preview-runtime-audit.py --timers
