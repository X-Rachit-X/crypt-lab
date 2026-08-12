#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║       Crypt Lab IDS — Attack Simulator CLI              ║
# ║  Usage:  ./simulate.sh [scenario]                       ║
# ║          ./simulate.sh  (interactive menu)              ║
# ╚══════════════════════════════════════════════════════════╝

PORT="${PORT:-8000}"
BASE="http://localhost:${PORT}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
PURPLE='\033[0;35m'

# ── Check server is up ────────────────────────────────────────
if ! curl -sf "${BASE}/api/health" >/dev/null 2>&1; then
  echo -e "${RED}[✗]${RESET} Server not running on port ${PORT}."
  echo -e "    Start it first with: ${BOLD}./run.sh${RESET}"
  exit 1
fi

run_scenario() {
  local scenario="$1"
  local label="$2"
  local colour="$3"

  echo ""
  echo -e "${colour}${BOLD}  ► Launching: ${label}${RESET}"
  RESP=$(curl -sf -X POST "${BASE}/api/simulate" \
    -H "Content-Type: application/json" \
    -d "{\"scenario\":\"${scenario}\"}" 2>&1) || {
    echo -e "${RED}[✗]${RESET} Request failed — is the server running?"
    exit 1
  }
  echo -e "${GREEN}[✓]${RESET} Scenario started → waiting for detection..."
  echo ""

  # Poll /api/alerts until a new alert appears (max 20s)
  BEFORE=$(curl -sf "${BASE}/api/alerts" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('alerts', [])))" 2>/dev/null || echo 0)
  for i in $(seq 1 35); do
    sleep 1
    printf "\r  ${CYAN}Detecting...${RESET} %ds" "$i"
    AFTER=$(curl -sf "${BASE}/api/alerts" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('alerts', [])))" 2>/dev/null || echo 0)
    if [[ "$AFTER" -gt "$BEFORE" ]]; then
      echo ""
      echo -e "${GREEN}${BOLD}  ✓ Alert detected!${RESET}"
      echo ""
      # Show the latest alert
      curl -sf "${BASE}/api/alerts" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d.get('alerts'):
    a = d['alerts'][0]
    print(f\"  Attack Type : {a.get('attack_type','?')}\")
    print(f\"  Source IP   : {a.get('src_ip','?')}\")
    print(f\"  Location    : {a.get('geo_city','?')}, {a.get('geo_country','?')}\")
    print(f\"  Severity    : {a.get('severity','?')}\")
    print(f\"  Confidence  : {int(a.get('confidence',0)*100)}%\")
    cms = a.get('countermeasures', [])
    if cms:
        print(f'  Countermeasures:')
        for i,c in enumerate(cms[:3], 1):
            print(f'    {i}. {c}')
"
      echo ""
      echo -e "  ${CYAN}View full dashboard → ${BOLD}http://localhost:${PORT}${RESET}"
      return 0
    fi
  done
  echo ""
  echo -e "${YELLOW}[!]${RESET} No alert yet — check the server terminal for errors."
}

menu() {
  echo ""
  echo -e "${CYAN}${BOLD}  ╔══════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}${BOLD}  ║   🔐 Crypt Lab IDS — Simulator       ║${RESET}"
  echo -e "${CYAN}${BOLD}  ╚══════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${BOLD}Choose a scenario:${RESET}"
  echo ""
  echo -e "  ${CYAN}1)${RESET} 🔍 Port Scan         — sequential port probe"
  echo -e "  ${RED}2)${RESET} 💥 DoS Flood          — high-volume single-source flood"
  echo -e "  ${YELLOW}3)${RESET} 🔑 Brute Force SSH   — repeated failed SSH auths"
  echo -e "  ${PURPLE}4)${RESET} 🌐 Web Scan           — HTTP directory/vuln scan"
  echo -e "  ${RED}5)${RESET} ☠️  DDoS               — distributed multi-source flood"
  echo -e "  ${BOLD}6)${RESET} ⚡  Run ALL scenarios   — one after another"
  echo -e "  ${BOLD}q)${RESET} Quit"
  echo ""
  printf "  Enter choice: "
  read -r choice
  echo ""

  case "$choice" in
    1) run_scenario "PORT_SCAN"     "Port Scan"       "$CYAN"   ;;
    2) run_scenario "DOS_FLOOD"     "DoS Flood"       "$RED"    ;;
    3) run_scenario "BRUTE_FORCE_SSH" "Brute Force SSH" "$YELLOW" ;;
    4) run_scenario "WEB_SCAN"      "Web Scan"        "$PURPLE" ;;
    5) run_scenario "DDOS"          "DDoS"            "$RED"    ;;
    6)
      run_scenario "PORT_SCAN"     "Port Scan"       "$CYAN"
      sleep 2
      run_scenario "DOS_FLOOD"     "DoS Flood"       "$RED"
      sleep 2
      run_scenario "BRUTE_FORCE_SSH" "Brute Force SSH" "$YELLOW"
      sleep 2
      run_scenario "WEB_SCAN"      "Web Scan"        "$PURPLE"
      sleep 2
      run_scenario "DDOS"          "DDoS"            "$RED"
      ;;
    q|Q) echo "Bye!"; exit 0 ;;
    *) echo -e "${YELLOW}[!]${RESET} Invalid choice."; exit 1 ;;
  esac
}

# ── Direct scenario from CLI arg ──────────────────────────────
if [[ $# -gt 0 ]]; then
  case "${1^^}" in
    PORT_SCAN)      run_scenario "PORT_SCAN"       "Port Scan"       "$CYAN"   ;;
    DOS_FLOOD)      run_scenario "DOS_FLOOD"       "DoS Flood"       "$RED"    ;;
    BRUTE_FORCE_SSH) run_scenario "BRUTE_FORCE_SSH" "Brute Force SSH" "$YELLOW" ;;
    WEB_SCAN)       run_scenario "WEB_SCAN"        "Web Scan"        "$PURPLE" ;;
    DDOS)           run_scenario "DDOS"            "DDoS"            "$RED"    ;;
    ALL)
      for s in PORT_SCAN DOS_FLOOD BRUTE_FORCE_SSH WEB_SCAN DDOS; do
        run_scenario "$s" "$s" "$CYAN"
        sleep 3
      done
      ;;
    *)
      echo -e "${RED}[✗]${RESET} Unknown scenario: $1"
      echo "    Valid: PORT_SCAN, DOS_FLOOD, BRUTE_FORCE_SSH, WEB_SCAN, DDOS, ALL"
      exit 1
      ;;
  esac
else
  menu
fi
