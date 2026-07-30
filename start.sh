#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Создаю изолированное окружение BanHelper…"
  python3 -m venv "$SCRIPT_DIR/.venv"
  "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi
exec "$PYTHON_BIN" "$SCRIPT_DIR/run.py"
