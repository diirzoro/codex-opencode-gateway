#!/usr/bin/env sh
set -eu

binary=${OPENCODE_BINARY:-opencode}
if [ -x "$binary" ]; then
  resolved=$binary
else
  resolved=$(command -v "$binary" 2>/dev/null || true)
fi
if [ -z "$resolved" ] || [ ! -x "$resolved" ]; then
  echo "OpenCode executable is unavailable; set OPENCODE_BINARY to its installed path." >&2
  exit 1
fi

version=$("$resolved" --version 2>/dev/null | tr -d '\r' | head -n 1)
case "$version" in
  *1.18.31*|*1.18.32*) ;;
  *) echo "Unsupported OpenCode version: $version (expected 1.18.31 or 1.18.32)." >&2; exit 1 ;;
esac

printf 'OpenCode CLI is available: %s (%s)\n' "$resolved" "$version"
printf 'Gateway runtime mode must remain disabled until workspace isolation is approved.\n'
