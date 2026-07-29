#!/usr/bin/env bash
# Orbis setup — Linux / macOS.
# The real logic lives in setup.py so Windows and Unix share one implementation.
set -euo pipefail
cd "$(dirname "$0")"

for py in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    exec "$py" setup.py "$@"
  fi
done

echo "Python 3.11+ is required but was not found on PATH." >&2
echo "Install it, then re-run ./setup.sh" >&2
exit 1
