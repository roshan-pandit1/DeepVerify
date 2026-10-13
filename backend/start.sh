#!/bin/bash
# No dependency installation, reload server, or legacy imports at startup.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [[ -n "${DEEPVERIFY_PYTHON:-}" ]]; then
  PYTHON="$DEEPVERIFY_PYTHON"
elif [[ -x ../.venv/bin/python ]]; then
  PYTHON=../.venv/bin/python
else
  PYTHON=python3
fi
if ! "$PYTHON" -c 'import uvicorn, dotenv, fastapi, bs4' >/dev/null 2>&1; then
  echo 'Install backend/requirements-investigation.txt in .venv, or set DEEPVERIFY_PYTHON to that interpreter.' >&2
  exit 1
fi
exec "$PYTHON" -m investigation.launch "${@:-api}"
