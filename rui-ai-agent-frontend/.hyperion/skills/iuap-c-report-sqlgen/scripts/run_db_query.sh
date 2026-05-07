#!/usr/bin/env bash
# Run db_query.py with proper venv handling
# Usage: ./run_db_query.sh [--env-file PATH] [--config PATH] --sql-file <file>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -x "${HERE}/.venv/bin/python" ]]; then
  exec "${HERE}/.venv/bin/python" "${HERE}/db_query.py" "$@"
fi
exec python3 "${HERE}/db_query.py" "$@"
