#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY="$SCRIPT_DIR/.venv/bin/python"

show_error() {
  local msg="$1"
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="Book Reader" --text="$msg" || true
  elif command -v xmessage >/dev/null 2>&1; then
    xmessage -center "$msg" || true
  fi
  echo "$msg" >&2
}

if [[ ! -x "$PY" ]]; then
  show_error "Python virtualenv not found at: $PY\n\nCreate it first:\n  python -m venv .venv\n  .venv/bin/pip install -r requirements.txt"
  exit 1
fi

exec "$PY" scripts/run_gui.py
