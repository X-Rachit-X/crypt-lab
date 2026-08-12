# 🔐 Crypt Lab IDS — AI-Powered Intrusion Detection System

> **A real-time network Intrusion Detection System with a live web dashboard, ML-based attack classification, Gemini AI countermeasures, AES-256-GCM encrypted alert storage, geo-location mapping, and an attack simulator.**

---

## 📋 Table of Contents

1. [What Was Built](#what-was-built)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Setup & Installation](#setup--installation)
5. [Configuration (.env)](#configuration-env)
6. [Running the Server](#running-the-server)
7. [Using the Dashboard](#using-the-dashboard)
8. [Attack Simulator](#attack-simulator)
9. [REST API Reference](#rest-api-reference)
10. [WebSocket Feeds](#websocket-feeds)
11. [What You Still Need to Do](#what-you-still-need-to-do)
12. [Troubleshooting](#troubleshooting)

---

## What Was Built

This project was built from scratch by an AI agent based on the `crypt_lab_agent_brief_v3.md` specification. Here is a complete record of everything that was created and fixed:

### ✅ Backend (Python / FastAPI)

| File | Lines | What it does |
|------|-------|--------------|
| `main.py` | 1341 | FastAPI app: all REST endpoints, WebSocket feeds, startup lifecycle, detection loop |
| `config.py` | 26 | Loads all settings from `.env` via `python-dotenv` |
| `ids/capture.py` | 117 | Scapy packet sniffer — captures raw packets on the configured interface |
| `ids/aggregator.py` | 191 | Groups packets into 5-second flow windows, extracts 19 ML features |
| `ids/engine.py` | 98 | Loads the RandomForest `.pkl` model, classifies flows, returns attack type + confidence |
| `ids/llm.py` | 185 | Calls Google Gemini API for AI-generated technical summary and countermeasures |
| `ids/geo.py` | 90 | Looks up IP geo-location via ipinfo.io (city, country, lat/lon) |
| `ids/alerts.py` | 96 | AES-256-GCM encrypts alert payloads; assembles the full alert object |
| `ids/db.py` | 132 | SQLite storage — `init_db()`, `save_alert()`, `get_alerts()`, `get_stats()` |
| `ids/log_capture.py` | 148 | Watchdog file watcher — tails `/var/log/auth.log`, syslog, nginx access log |
| `simulator/templates.py` | 164 | 5 attack scenario templates with realistic IPs, ports, packet patterns |
| `simulator/simulator.py` | 75 | Injects simulated flows into the aggregator's queue, posts progress via WebSocket |

### ✅ Frontend (Vanilla JS + Tailwind + Leaflet + Chart.js)

| File | Lines | What it does |
|------|-------|--------------|
| `static/index.html` | 234 | 3-column CSS Grid dashboard — 6 panels, Tailwind dark theme |
| `static/js/app.js` | 291 | Dashboard controller: clock, WebSocket client, alert table, chart, log viewer |
| `static/js/map.js` | 94 | Leaflet map with CartoDB dark tiles, animated attack origin markers |
| `static/js/simulator.js` | 125 | Simulator panel UI: button wiring, progress bar, detection feedback |

### ✅ ML Model

| File | What it does |
|------|--------------|
| `model/ids_model.pkl` | Pre-trained scikit-learn `Pipeline(StandardScaler + RandomForestClassifier)` |
| `model/label_encoder.pkl` | Maps numeric class indices to attack type labels |
| `model/feature_list.pkl` | Ordered list of the 19 features the model expects |
| `create_placeholder_model.py` | Script that regenerates placeholder `.pkl` files if the model folder is missing |

### ✅ What Was Fixed in the Last Session

| Problem | Root Cause | Fix Applied |
|---------|-----------|-------------|
| Frontend completely broken / glitched | `index.html` and `app.js` had two separate files merged **side-by-side on every single line** (old CyberGym code interleaved with new IDS code) | Rewrote both files from scratch via Python/shell write — bypassed the broken VS Code tool |
| Database read-only error | `ids_alerts.db` was owned by `root` from a previous `sudo uvicorn` run | `sudo chown $USER ids_alerts.db` |
| `IDS_AES_KEY` blank in `.env` | Key was never generated | Generated 32-byte random hex key via `os.urandom(32)` |
| Wrong network interface (`eth0` not found) | Default `.env` had `eth0`, machine uses `enp3s0` | Updated `CAPTURE_INTERFACE=enp3s0` in `.env` |

---

## Architecture

```
Browser ──── WebSocket /ws/ids-feed ────► main.py detection_loop()
         └── WebSocket /ws/log-feed ────►      │
         └── REST GET /api/*         ◄──────────┘
                                                │
                          ┌─────────────────────┼──────────────────────┐
                          │                     │                      │
                     ids/capture.py      ids/log_capture.py    simulator/
                     (Scapy sniffer)     (Watchdog log tail)   (5 scenarios)
                          │
                     ids/aggregator.py
                     (19-feature flows)
                          │
                     ids/engine.py
                     (RandomForest ML)
                          │
              ┌───────────┴───────────┐
         ids/llm.py              ids/geo.py
         (Gemini AI)              (ipinfo.io)
              └───────────┬───────────┘
                     ids/alerts.py
                     (AES-256-GCM)
                          │
                     ids/db.py
                     (SQLite)
                          │
                  ──► broadcast to
                      all WS clients
```

---

## Project Structure

```
cyber-gym-main/
├── .env                        # Secrets & config (NEVER commit)
├── .gitignore
├── config.py                   # Settings loader
├── main.py                     # FastAPI app (entry point)
├── requirements.txt
├── create_placeholder_model.py # Regenerate model .pkl files
├── ids/
│   ├── __init__.py
│   ├── aggregator.py           # Flow feature extraction
│   ├── alerts.py               # AES-256-GCM + alert builder
│   ├── capture.py              # Scapy packet capture
│   ├── db.py                   # SQLite persistence
│   ├── engine.py               # ML classifier
│   ├── geo.py                  # IP geolocation
│   ├── llm.py                  # Gemini AI enrichment
│   └── log_capture.py          # Log file watcher
├── simulator/
│   ├── __init__.py
│   ├── simulator.py            # Scenario runner
│   └── templates.py            # 5 attack templates
├── model/
│   ├── ids_model.pkl           # RandomForest pipeline
│   ├── label_encoder.pkl       # Class label mapping
│   └── feature_list.pkl        # Feature name list
├── static/
│   ├── index.html              # Main dashboard
│   ├── css/styles.css
│   └── js/
│       ├── app.js              # Dashboard controller
│       ├── map.js              # Leaflet attack map
│       └── simulator.js        # Simulator panel
└── scripts/
    └── dev_server.sh           # Dev startup script
```

---

## Setup & Installation

### 1. Clone / Enter the project

```bash
cd /home/aka/Videos/Crypto/cyber-gym-main
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure `.env`

Copy the template and fill in your keys (see [Configuration](#configuration-env) below):

```bash
# .env is already present — edit it:
nano .env
```

### 5. (Optional) Regenerate the ML model

If `model/` is missing or corrupted:

```bash
python3 create_placeholder_model.py
```

---

## Configuration (.env)

```ini
# ── Google Gemini AI ───────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here   # Get from aistudio.google.com
GEMINI_MODEL=gemini-2.5-flash             # or gemini-1.5-pro

# ── Behavior ──────────────────────────────────────────────────
ANALYSIS_ENABLED=true
ANALYSIS_SAMPLE_SIZE=2000
ANALYSIS_DEBOUNCE_MS=2500
DEBUG=false

# ── IDS ───────────────────────────────────────────────────────
IDS_MODEL_DIR=./model
IDS_AES_KEY=<64-char hex key>             # Generate: python3 -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())"
CAPTURE_INTERFACE=enp3s0                  # Find yours: ip link show
LOG_PATHS=/var/log/syslog,/var/log/auth.log,/var/log/nginx/access.log
IPINFO_TOKEN=                             # Optional: free tier at ipinfo.io
```

> **Generate a new AES key:**
> ```bash
> python3 -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())"
> ```

> **Find your network interface:**
> ```bash
> ip link show
> ```

---

## Running the Server

### Standard mode (simulator only — no root needed)

```bash
cd /home/aka/Videos/Crypto/cyber-gym-main
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Live packet capture mode (requires root for raw socket)

```bash
sudo venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
# Then fix DB ownership if needed:
sudo chown $USER:$USER ids_alerts.db
```

### What happens on startup

1. `init_db()` — creates `ids_alerts.db` with the alerts table
2. `load_model()` — loads `model/ids_model.pkl`, `label_encoder.pkl`, `feature_list.pkl`
3. `FlowAggregator` starts — 5-second flow window processor
4. Packet capture thread starts (requires root; gracefully skips if not root)
5. Log capture thread starts (watchdog on configured LOG_PATHS)
6. `detection_loop()` asyncio task starts — polls flows every 2s, classifies, enriches, stores, broadcasts

---

## Using the Dashboard

Open **http://localhost:8000** in your browser.

### Panel Guide

```
┌─────────────────────────────────────┬──────────────────────┐
│  🔴 Live Alert Feed                 │  �� Countermeasures   │
│  Real-time table of all detected    │  AI-generated steps   │
│  attacks. Click a row to expand     │  for the latest High/ │
│  geo details + countermeasures.     │  Medium threat.       │
├─────────────────────────────────────┤                       │
│  🟢 Attack Map                      │                       │
│  World map — markers show where     │                       │
│  attacks are coming from.           │                       │
├─────────────────────────────────────┼──────────────────────┤
│  📋 System Log Viewer               │  🟣 Distribution      │
│  Live color-coded log lines from    │  Doughnut chart —     │
│  auth.log, syslog, nginx.           │  attack type counts.  │
│  [⏸ Pause] button to freeze.        │                       │
├─────────────────────────────────────┼──────────────────────┤
│                                     │  🟢 Attack Simulator  │
│                                     │  5 scenario buttons + │
│                                     │  progress bar.        │
└─────────────────────────────────────┴──────────────────────┘
```

### Status Indicator (top-right)

| Colour | Meaning |
|--------|---------|
| 🟢 Green pulse | WebSocket connected — live feed active |
| 🟡 Amber pulse | Connecting / reconnecting |
| 🔴 Red | Disconnected — will auto-reconnect in 3s |

  "gemini": { "enabled": true, "model": "gemini-2.5-flash" },
  "connections": { "vm1": 0, "vm2": 0 }
}
```

### `GET /api/alerts`
All stored alerts, newest first.
---

## Attack Simulator

The simulator injects pre-crafted network flow data directly into the detection pipeline — **no real attacks are sent**.

### From the Dashboard

Click any button in the **Attack Simulator** panel (bottom-right corner).

### From the Terminal (curl)

```bash
# Port Scan — sequential probe of ports 1–1024
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"PORT_SCAN"}'

# DoS Flood — high-volume single-source UDP/TCP flood
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"DOS_FLOOD"}'

# Brute Force SSH — repeated failed auth on port 22
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"BRUTE_FORCE_SSH"}'

# Web Scan — HTTP directory traversal / vuln scan
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"WEB_SCAN"}'

# DDoS — distributed multi-source flood
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"DDOS"}'
```

**Expected flow:** Simulation starts → ~5–10 seconds → detection loop classifies flows → alert appears in dashboard table, map, chart, and countermeasures panel simultaneously.

---

## REST API Reference

All endpoints return JSON.

### `GET /api/health`
Server and Gemini status.
```json
{
  "status": "ok",
  "gemini": { "enabled": true, "model": "gemini-2.5-flash" },
  "connections": { "vm1": 0, "vm2": 0 }
}
```

### `GET /api/alerts`
All stored alerts, newest first.
```json
{
  "ok": true,
  "alerts": [
    {
      "id": "uuid",
      "timestamp": "2026-03-10T06:23:18.918936+00:00",
      "attack_type": "Port Scan",
      "src_ip": "185.220.101.45",
      "dst_ip": "192.168.1.100",
      "severity": "Medium",
      "confidence": 0.95,
      "geo_lat": 52.52,
      "geo_lon": 13.41,
      "geo_city": "Berlin",
      "geo_country": "DE",
      "alert_message": "Port Scan detected from 185.220.101.45 with 95% confidence.",
      "countermeasures": ["Block IP at firewall", "..."],
      "technical_summary": "AI-generated analysis...",
      "encrypted_payload": "base64-AES-256-GCM..."
    }
  ]
}
```

### `GET /api/stats`
Attack type counts (feeds the doughnut chart).
```json
{ "ok": true, "stats": { "Port Scan": 3, "DoS": 1 } }
```

### `GET /api/map`
Alerts that have valid geo-coordinates (for the Leaflet map).
```json
{ "ok": true, "markers": [ { "lat": 52.52, "lon": 13.41, "attack_type": "Port Scan", ... } ] }
```

### `GET /api/logs`
Last 200 parsed log events from watched log files.
```json
{ "ok": true, "logs": [ { "log_type": "auth_failure", "raw_line": "...", "timestamp": 1741234567 } ] }
```

### `POST /api/simulate`
Inject a simulated attack scenario.

**Request body:**
```json
{ "scenario": "PORT_SCAN" }
```
Valid values: `PORT_SCAN`, `DOS_FLOOD`, `BRUTE_FORCE_SSH`, `WEB_SCAN`, `DDOS`

**Response:**
```json
{ "ok": true, "status": "started", "scenario": "PORT_SCAN", "expected_seconds": 5 }
```

---

## WebSocket Feeds

### `WS /ws/ids-feed`
Real-time IDS alert stream. Receives messages in the format:
```json
{
  "type": "ids_alert",
  "data": { /* full alert object — same as /api/alerts */ }
}
```
Also receives simulator progress events:
```json
{ "type": "sim_progress", "data": { "scenario": "PORT_SCAN", "pct": 60 } }
```

### `WS /ws/log-feed`
Real-time log event stream:
```json
{
  "type": "log",
  "data": { "log_type": "auth_failure", "raw_line": "Mar 10 ...", "timestamp": 1741234567 }
}
```

---

## What You Still Need to Do

These are tasks that require your input or external services:

### 🔑 1. Gemini API Key (Already set but verify it works)
Your `.env` already has `GEMINI_API_KEY` set. The current model `gemini-2.5-flash` is deprecated — you should update it:
```ini
GEMINI_MODEL=gemini-2.0-flash
```
Or get a new key at [aistudio.google.com](https://aistudio.google.com) if needed.

> ⚠️ The `google-generativeai` package itself is also deprecated. To silence the warning and future-proof the code, you would need to migrate `ids/llm.py` to use `google-genai` package instead. Not urgent — everything still works.

### 🌐 2. ipinfo.io Token (Optional — for better geo-location)
Currently blank — the free tier works without a token but has rate limits (50k requests/month).
Get a free token at [ipinfo.io](https://ipinfo.io/signup) and set:
```ini
IPINFO_TOKEN=your_token_here
```

### 🖧 3. Live Packet Capture (Optional — requires root)
To capture real traffic on your network (not just simulated):
```bash
sudo venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```
Then immediately fix DB ownership:
```bash
sudo chown $USER:$USER ids_alerts.db
```

### 🤖 4. Train a Real ML Model (Optional — improves accuracy)
The current model is a placeholder trained on dummy data. To train on real network traffic:
```bash
# Collect labeled PCAP data (e.g. from CIC-IDS-2018 dataset)
# Re-train in train_model.py (not yet written — you would need to create this)
# Replace model/ids_model.pkl, label_encoder.pkl, feature_list.pkl
```

### 📊 5. Add `/var/log` Access (Recommended)
The log viewer watches `/var/log/auth.log`, `/var/log/syslog`, and `/var/log/nginx/access.log`.
These files need to be readable by your user:
```bash
sudo chmod o+r /var/log/auth.log /var/log/syslog
# Or add yourself to the adm group:
sudo usermod -aG adm $USER
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Interface 'eth0' not found` | Wrong interface in `.env` | Run `ip link show`, set `CAPTURE_INTERFACE` |
| `attempt to write a readonly database` | DB owned by root | `sudo chown $USER:$USER ids_alerts.db` |
| `[Errno 98] Address already in use` | Port 8000 taken | `fuser -k 8000/tcp` then restart |
| No alerts after simulation | Detection loop takes ~5–10s | Wait and check server terminal for errors |
| Gemini countermeasures are generic fallback | API timeout or bad key | Check `GEMINI_API_KEY` in `.env` |
| `google.generativeai FutureWarning` | Package deprecated | Non-breaking warning — migrate to `google-genai` when convenient |
| Packet capture fails silently | Not running as root | Use `sudo venv/bin/uvicorn ...` for live capture |
| Map markers not appearing | Alert has `geo_lat=0, geo_lon=0` | Local/private IPs can't be geo-located — expected behaviour |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI + Uvicorn |
| Real-time | WebSockets (native FastAPI) |
| AI alert enrichment | Google Gemini (`google-genai` SDK) |
| AI chatbot | puter.js → GPT-4o-mini (free, no API key) |
| ML classifier | scikit-learn RandomForest + StandardScaler |
| Network capture | Scapy |
| Encryption | `cryptography` — AES-256-GCM |
| Geo-location | ipinfo.io REST API |
| Log watching | watchdog (inotify) |
| Notifications | Telegram Bot API |
| Storage | SQLite (synchronous, thread-local connections) |
| Frontend | Vanilla JS + Tailwind CSS CDN |
| Map | Leaflet.js + CartoDB Dark tiles |
| Chart | Chart.js 4.4 Doughnut |
| Fonts | JetBrains Mono + Inter (Google Fonts) |

---

## 📚 Full Documentation

For complete technical documentation covering every component, library,
data flow, API, and design decision, see:

**[DOCUMENTATION.md](./DOCUMENTATION.md)**

Contents:
- Complete architecture diagram
- Every library explained (what it is, why it's used, how it's configured)
- Full data flow: raw packet → alert → dashboard
- ML model internals, 19 features, rule engine conditions
- Gemini AI integration (when called, rate limiting, caching, prompt)
- puter.js chatbot (architecture, system prompt, streaming)
- AES-256-GCM encryption details
- Complete REST API and WebSocket reference
- Database schema and useful queries
- Security considerations and known limitations

---

*Built by AI agent — Crypt Lab IDS v3 — March 2026*
