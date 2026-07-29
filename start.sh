#!/usr/bin/env bash
# Orbis — start the backend and frontend together (Linux / macOS).
# Shares its implementation with Windows via start.py.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x venv/bin/python ]; then
  exec venv/bin/python start.py "$@"
fi

for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" start.py "$@"; fi
done

echo "Python not found — run ./setup.sh first." >&2
exit 1
