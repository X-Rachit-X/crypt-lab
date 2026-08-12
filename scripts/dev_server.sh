#!/usr/bin/env bash
set -euo pipefail

# Auto-pick a free port and run uvicorn in background
# Usage:
#   HOST=0.0.0.0 PORT=8000 scripts/dev_server.sh
# Outputs:
#   - devserver.pid: PID of uvicorn
#   - devserver.port: chosen port
#   - uvicorn.log: server logs

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

HOST="${HOST:-0.0.0.0}"
START_PORT="${PORT:-8000}"
MAX_TRIES=100

# Pick interpreter (prefer venv python)
PY="$PROJECT_DIR/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then PY="$(command -v python3)"; else PY="$(command -v python)"; fi
fi

# Ensure deps (if missing)
if ! "$PY" - << 'PY'
try:
    import uvicorn, fastapi  # noqa
except Exception as e:
    raise SystemExit(1)
PY
then
  echo "[INFO] Installing Python dependencies..."
  "$PY" -m pip install -U pip setuptools wheel >/dev/null
  "$PY" -m pip install -U fastapi "uvicorn[standard]" python-dotenv google-generativeai paramiko psutil cryptography >/dev/null
  # Ensure google-generativeai is recent enough for 1.5 models
fi

# Find a free port
CHOSEN_PORT=""
for i in $(seq 0 $MAX_TRIES); do
  p=$((START_PORT + i))
  # Check with ss or lsof
  if command -v ss >/dev/null 2>&1; then
    if ! ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ":$p$"; then CHOSEN_PORT="$p"; break; fi
  else
    if ! lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1; then CHOSEN_PORT="$p"; break; fi
  fi
done

if [[ -z "$CHOSEN_PORT" ]]; then
  echo "[ERROR] Could not find a free port starting from $START_PORT"
  exit 1
fi

echo "$CHOSEN_PORT" > devserver.port

# Start server in background
if [[ -f devserver.pid ]]; then
  OLD_PID=$(cat devserver.pid || true)
  if [[ -n "${OLD_PID:-}" ]] && ps -p "$OLD_PID" >/dev/null 2>&1; then
    echo "[INFO] Previous server (PID $OLD_PID) still running. Stopping..."
    kill -TERM "$OLD_PID" || true
    sleep 1
  fi
fi

# Use python -m uvicorn to avoid bad shebangs
nohup "$PY" -m uvicorn main:app --host "$HOST" --port "$CHOSEN_PORT" --no-access-log > uvicorn.log 2>&1 &
PID=$!
echo $PID > devserver.pid

# Wait briefly to confirm it bound to the port
sleep 1
if command -v curl >/dev/null 2>&1; then
  if ! curl -sSf "http://127.0.0.1:$CHOSEN_PORT/" >/dev/null 2>&1; then
    echo "[WARN] Server started (PID $PID) but did not respond yet. Check uvicorn.log if needed."
  fi
fi

echo "[OK] Server running: http://127.0.0.1:$CHOSEN_PORT/ (PID $PID)"
