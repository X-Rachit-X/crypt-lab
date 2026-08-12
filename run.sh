#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║          Crypt Lab IDS — Start Script                   ║
# ║  Usage:  ./run.sh [--port 8000] [--capture]             ║
# ║          ./run.sh stop                                  ║
# ╚══════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────
PORT=8000
CAPTURE=false
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.ids_server.pid"

# ── Pretty colours ────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

step()  { echo -e "${CYAN}[→]${RESET} $*"; }
ok()    { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
fail()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

# ── Handle 'stop' command ─────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
  echo -e "${CYAN}${BOLD}  Stopping Crypt Lab IDS...${RESET}"
  # Try PID file first
  if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID" && ok "Stopped server (PID $PID)"
    else
      warn "PID $PID is not running"
    fi
    rm -f "$PID_FILE"
  fi
  # Also kill any uvicorn on the port as fallback
  if command -v fuser &>/dev/null; then
    OLD=$(fuser "${PORT}/tcp" 2>/dev/null || true)
    [[ -n "$OLD" ]] && { fuser -k "${PORT}/tcp" 2>/dev/null || true; ok "Killed process on port $PORT"; }
  fi
  exit 0
fi

# ── Parse args ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)    PORT="$2"; shift 2 ;;
    --capture) CAPTURE=true; shift ;;
    -h|--help)
      echo "Usage: ./run.sh [--port 8000] [--capture]"
      echo "       ./run.sh stop"
      echo ""
      echo "  --port     Port to listen on (default: 8000)"
      echo "  --capture  Enable live packet capture (requires sudo)"
      echo "  stop       Stop a running server"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

cd "$DIR"

banner() {
  echo -e ""
  echo -e "${CYAN}${BOLD}  ╔═══════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}${BOLD}  ║     🔐 Crypt Lab IDS  v3.0            ║${RESET}"
  echo -e "${CYAN}${BOLD}  ║     AI-Powered Intrusion Detection    ║${RESET}"
  echo -e "${CYAN}${BOLD}  ╚═══════════════════════════════════════╝${RESET}"
  echo -e ""
}

banner

# ── 1. Check Python / venv ────────────────────────────────────
step "Checking Python environment..."
if [[ -f "$DIR/venv/bin/python" ]]; then
  PY="$DIR/venv/bin/python"
  UV="$DIR/venv/bin/uvicorn"
  ok "Found venv: $PY"
else
  warn "No venv found — creating one..."
  python3 -m venv "$DIR/venv"
  PY="$DIR/venv/bin/python"
  UV="$DIR/venv/bin/uvicorn"
  ok "venv created"
fi

# ── 2. Install / check dependencies ──────────────────────────
step "Checking dependencies..."
if ! "$PY" -c "import fastapi, uvicorn, scapy, cryptography, sklearn" 2>/dev/null; then
  warn "Some packages missing — installing from requirements.txt..."
  "$PY" -m pip install -q -r "$DIR/requirements.txt"
  ok "Dependencies installed"
else
  ok "All dependencies present"
fi

# ── 3. Check .env ─────────────────────────────────────────────
step "Checking configuration..."
if [[ ! -f "$DIR/.env" ]]; then
  fail ".env file not found! Copy the example and fill in your keys."
fi

AES_KEY=$(grep -E '^IDS_AES_KEY=' "$DIR/.env" | cut -d= -f2)
if [[ -z "$AES_KEY" ]]; then
  warn "IDS_AES_KEY is blank — generating one now..."
  NEW_KEY=$("$PY" -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())")
  sed -i "s/^IDS_AES_KEY=$/IDS_AES_KEY=$NEW_KEY/" "$DIR/.env"
  ok "AES key generated and saved to .env"
else
  ok ".env looks good"
fi

# ── 4. Check model files ──────────────────────────────────────
step "Checking ML model..."
if [[ ! -f "$DIR/model/ids_model.pkl" ]]; then
  warn "Model files missing — regenerating placeholder..."
  "$PY" "$DIR/create_placeholder_model.py"
  ok "Placeholder model created"
else
  ok "Model files present"
fi

# ── 5. Fix DB ownership (common after sudo run) ───────────────
if [[ -f "$DIR/ids_alerts.db" ]]; then
  OWNER=$(stat -c '%U' "$DIR/ids_alerts.db")
  ME=$(whoami)
  if [[ "$OWNER" != "$ME" ]]; then
    warn "ids_alerts.db owned by '$OWNER' — fixing with sudo..."
    sudo chown "$ME":"$ME" "$DIR/ids_alerts.db" && ok "DB ownership fixed"
  fi
fi

# ── 6. Free up port if taken ──────────────────────────────────
step "Checking port $PORT..."
if command -v fuser &>/dev/null; then
  OLD_PID=$(fuser "${PORT}/tcp" 2>/dev/null || true)
  if [[ -n "$OLD_PID" ]]; then
    warn "Port $PORT is in use (PID $OLD_PID) — killing..."
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    sleep 1
  fi
fi
ok "Port $PORT is free"

# ── 7. Launch ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Dashboard →  http://localhost:${PORT}${RESET}"
echo -e "  To stop   →  ${CYAN}./run.sh stop${RESET}   or   ${CYAN}Ctrl+C${RESET}"
echo ""

if [[ "$CAPTURE" == "true" ]]; then
  echo -e "${YELLOW}  Live packet capture enabled — running with sudo${RESET}"
  echo -e "${YELLOW}  (You may be prompted for your password)${RESET}"
  echo ""
  sudo "$UV" main:app --host 0.0.0.0 --port "$PORT" &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  ok "Server started (PID $SERVER_PID)"
  wait "$SERVER_PID"
  # Fix DB ownership after sudo
  sudo chown "$(whoami)":"$(whoami)" "$DIR/ids_alerts.db" 2>/dev/null || true
else
  "$UV" main:app --host 0.0.0.0 --port "$PORT" &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  ok "Server started (PID $SERVER_PID) — stop with: ./run.sh stop"
  wait "$SERVER_PID"
fi

rm -f "$PID_FILE"
