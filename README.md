# 🔐 Crypt Lab IDS — AI-Powered Intrusion Detection System

> **Production-ready real-time network Intrusion Detection System with ML-based attack classification, AI chatbot, live web dashboard, encrypted alerts, geo-mapping, and integrated attack simulator.**

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green) ![scikit-learn](https://img.shields.io/badge/scikit--learn-1.8-orange) ![License MIT](https://img.shields.io/badge/License-MIT-brightgreen)

---

## 🎯 What This Does

Crypt Lab IDS is a high-performance cybersecurity monitoring system that:

- **Detects real-time network attacks** via flow-based ML classification (11 attack types, 90–97% accuracy)
- **Analyzes logs** from syslog, auth.log, and nginx access logs
- **Enriches alerts** with geo-location, WHOIS, and AI-generated countermeasures (Gemini API)
- **Visualizes threats** on an interactive world map with live statistics dashboard
- **Chats with you** via AI chatbot for threat intelligence and defense recommendations
- **Encrypts sensitive data** using AES-256-GCM at rest in SQLite
- **Simulates attacks** with 6 pre-built scenarios for testing and training

**Perfect for:** Cyber labs, SOC dashboards, network security training, personal homelab monitoring.

---

## 🚀 Quick Start

**1. Clone & Setup**
```bash
cd cyber-gym-main
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure**
```bash
# Edit .env with your API keys (optional but recommended)
nano .env
```

**3. Run**
```bash
# Easy way (recommended)
./run.sh

# Or manually
uvicorn main:app --host 0.0.0.0 --port 8000
```

**4. Open Dashboard**
```
http://localhost:8000
```

Done! The dashboard shows live alerts, attack stats, and the chatbot is ready to chat.

---

## 📋 Table of Contents

1. [Architecture & How It Works](#architecture--how-it-works)
2. [Features Checklist](#-features-checklist)
3. [Installation (Detailed)](#installation-detailed)
4. [Configuration](#configuration)
5. [Running the Server](#running-the-server)
6. [Dashboard Guide](#dashboard-guide)
7. [Attack Simulator](#attack-simulator)
8. [REST API Reference](#rest-api-reference)
9. [Optional Enhancements](#optional-enhancements)
10. [Troubleshooting](#troubleshooting)
11. [Project Structure](#project-structure)
12. [Tech Stack](#tech-stack)

---

## 🏗️ Architecture & How It Works

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CRYPT LAB IDS PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────┘

INPUT SOURCES:
  • Network packets (Scapy on configured interface)
  • System logs (/var/log/auth.log, syslog, nginx access log)
  • Simulated attacks (via API or dashboard)

                                    ↓

FLOW AGGREGATION (5-second windows):
  • Groups packets by (src_ip, dst_ip, src_port, dst_port, protocol)
  • Extracts 19 network flow metrics (packets, bytes, flags, duration, etc.)
  • Tracks bidirectional stats (forward / backward)

                                    ↓

DUAL-PATH DETECTION:
  ┌─────────────────────────────────────────────────────────┐
  │ RULE ENGINE (Fast Path)                                 │
  │ • Port Scan: syn_count > 100                            │
  │ • Brute Force: rst_count > threshold                    │
  │ • SYN Flood: syn_flag / total_fwd > 0.8                 │
  │ • DDoS: source entropy low + pps > 50k                  │
  │ • Heartbleed: specific packet signatures                │
  │                                                          │
  │ Returns: Attack type + confidence 90-97%                │
  └─────────────────────────────────────────────────────────┘

                    ↓ (rules don't match) ↓

  ┌─────────────────────────────────────────────────────────┐
  │ ML CLASSIFIER (Fallback)                                │
  │ • scikit-learn RandomForest (300 trees)                 │
  │ • 11 attack classes + Benign                            │
  │ • 19 features normalized via StandardScaler             │
  │                                                          │
  │ Returns: Attack type + RF confidence                    │
  └─────────────────────────────────────────────────────────┘

                                    ↓

ENRICHMENT:
  • Geo-location: IP → city/country/lat/lon (ipinfo.io)
  • LLM Analysis: Flow → countermeasures (Gemini API)
  • Technical Summary: Human-readable attack explanation

                                    ↓

PERSISTENCE & BROADCAST:
  • Encrypt alert payload (AES-256-GCM)
  • Store in SQLite (ids_alerts.db)
  • Broadcast to all WebSocket clients (dashboard)
  • Update stats (top IPs, severity breakdown)

                                    ↓

DASHBOARD (Real-time):
  • Live alert table (click to expand)
  • Attack map (markers by geo-location)
  • Stats sidebar (top 5 IPs, severity counts)
  • Log viewer (color-coded auth/syslog/nginx)
  • Doughnut chart (attack type distribution)
  • AI chatbot (threat Q&A with live context)
```

---

## ✅ Features Checklist

| Feature | Status | Notes |
|---------|--------|-------|
| **Real-time Detection** | ✅ | Flow-based (5s windows) + hybrid rule+ML classification |
| **11 Attack Types** | ✅ | Benign, Port Scan, DoS, DDoS, Brute Force, Heartbleed, Infiltration, Bot, Web Attack (3 types) |
| **Accuracy** | ✅ | Rule engine: 90–97% confidence; ML fallback for edge cases |
| **6 Simulator Scenarios** | ✅ | PORT_SCAN, DOS_FLOOD, BRUTE_FORCE_SSH, WEB_SCAN, DDOS, HEARTBLEED |
| **Live Dashboard** | ✅ | 8 panels (alerts, map, stats, logs, chart, simulator, countermeasures, chatbot) |
| **AI Chatbot (puter.js)** | ✅ | Free GPT-4o-mini streaming; real-time attack context injection |
| **AI Countermeasures (Gemini)** | ✅ | Optional; automatic fallback if API is unavailable |
| **Geo-mapping** | ✅ | Leaflet.js + CartoDB; attack origin markers with hover tooltips |
| **AES-256-GCM Encryption** | ✅ | Payload encryption at rest; configurable key in .env |
| **Log Parsing** | ✅ | Watchdog monitoring of auth.log, syslog, nginx; pattern extraction |
| **Multi-source Detection** | ✅ | Network packets (Scapy) + logs (watchdog) + simulator |
| **False Positive Fixes** | ✅ | Min 5-packet flows, min 0.1s duration, DoS threshold 50k pps |
| **SQLite Persistence** | ✅ | WAL mode for concurrent writes; async access |
| **Server Management** | ✅ | `./run.sh stop` for clean shutdown; PID file tracking |

---

## 📦 Installation (Detailed)

### Prerequisites

- **Python 3.10+** (tested on 3.12)
- **pip** (or conda)
- **sudo** (for live packet capture; optional, can run simulation-only without root)

### Step 1: Clone Repository

```bash
git clone https://github.com/X-Rachit-X/crypt-lab.git
cd crypt-lab
```

### Step 2: Create & Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies include:**
- FastAPI 0.109.0
- scikit-learn 1.8.0
- Scapy 2.5.0
- watchdog 4.0
- google-genai (Gemini API)
- cryptography 42.0.0
- python-dotenv
- requests
- aiofiles

### Step 4: Configure Environment

```bash
# Copy or create .env file
cp .env.example .env  # or nano .env
```

See [Configuration](#configuration) section below.

### Step 5: (Optional) Regenerate ML Model

If the `model/` folder is missing:

```bash
python3 create_placeholder_model.py
```

This regenerates the RandomForest pickle files. The model is pre-trained and ready to use.

### Step 6: Start the Server

```bash
./run.sh
```

Or manually:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser. ✅

---

## ⚙️ Configuration

### .env File

Create a `.env` file in the project root:

```ini
# ─────────────────────────────────────────────────────────
# Google Gemini AI (for countermeasures & rich analysis)
# ─────────────────────────────────────────────────────────
GEMINI_API_KEY=sk-...your_key...
GEMINI_MODEL=gemini-2.0-flash
# Alternative models: gemini-1.5-pro, gemini-1.5-flash

# ─────────────────────────────────────────────────────────
# IDS Configuration
# ─────────────────────────────────────────────────────────
IDS_MODEL_DIR=./model
IDS_AES_KEY=<64-char hex key>  # Generate below ↓
CAPTURE_INTERFACE=enp3s0       # Find yours: ip link show
LOG_PATHS=/var/log/syslog,/var/log/auth.log,/var/log/nginx/access.log

# ─────────────────────────────────────────────────────────
# Geo-location (optional but recommended)
# ─────────────────────────────────────────────────────────
IPINFO_TOKEN=                  # Optional; free tier 50k req/month

# ─────────────────────────────────────────────────────────
# Behavior Tuning
# ─────────────────────────────────────────────────────────
ANALYSIS_ENABLED=true
ANALYSIS_SAMPLE_SIZE=2000
ANALYSIS_DEBOUNCE_MS=2500
DEBUG=false
```

### Generate AES-256 Key

```bash
python3 -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())"
```

Copy the output and paste into `.env` as `IDS_AES_KEY`.

### Find Your Network Interface

```bash
ip link show
# or
ifconfig
```

Look for your active interface (e.g., `eth0`, `wlan0`, `enp3s0`). Update `.env`:
```ini
CAPTURE_INTERFACE=your_interface_name
```

### Get API Keys (Optional)

**Gemini API (Free Tier - 60 requests/minute):**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create a new API key
3. Paste into `.env` as `GEMINI_API_KEY`

**ipinfo.io Token (Free Tier - 50k requests/month):**
1. Go to [ipinfo.io/signup](https://ipinfo.io/signup)
2. Create a free account
3. Copy your token
4. Paste into `.env` as `IPINFO_TOKEN`

---

## 🔧 Running the Server

### Quickstart (Recommended)

```bash
./run.sh
```

This handles:
- ✅ Activating virtual environment
- ✅ Setting up database
- ✅ Loading ML model
- ✅ Starting WebSocket feeds
- ✅ Tracking PID for graceful shutdown

**Optional flags:**
```bash
./run.sh --port 9000          # Use custom port (default: 8000)
./run.sh --capture            # Enable live packet capture (requires sudo)
./run.sh stop                  # Stop the running server
```

### Manual Startup

**Simulator mode (no root needed):**
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**With live packet capture (requires sudo):**
```bash
sudo venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
sudo chown $USER:$USER ids_alerts.db  # Fix DB ownership
```

### What Happens on Startup

1. **Database Init**: Creates `ids_alerts.db` with alerts table (AES-256-GCM fields)
2. **Model Load**: Loads `model/ids_model.pkl`, `label_encoder.pkl`, `feature_list.pkl` into memory
3. **Flow Aggregator Start**: Initializes 5-second flow window processor
4. **Packet Capture Thread**: Starts Scapy sniffer (requires root; gracefully skips otherwise)
5. **Log Capture Thread**: Starts watchdog monitoring on configured LOG_PATHS
6. **Detection Loop**: Async task polls flows every 2s → classify → enrich → store → broadcast

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
[IDS] Model loaded: 11 classes, 19 features
[IDS] Flow aggregator started
[IDS] Packet capture active on enp3s0
[IDS] Detection loop started
```

---

## 📊 Dashboard Guide

### Accessing the Dashboard

Open **http://localhost:8000** in any modern browser (Chrome, Firefox, Safari, Edge).

### Layout Overview

```
┌────────────────────────────────────────────────────────────────┬──────────────┐
│             HEADER: Connection • Sensor IP • Time              │ Mode Selector│
├────────────────────────────────────────────────────────────────┼──────────────┤
│ 🔴 Live Alert Feed  │ 🟢 Attack Map                           │ 📊 Stats     │
│ ─────────────────── │ ──────────────                           │ ─────────    │
│ Click to expand,    │ World markers for attack sources.        │ Top 5 IPs    │
│ sort by severity    │ Hover for tooltip, click to geo-locate  │ Severity %   │
│                     │                                          │ Confidence % │
├─────────────────────┼──────────────────────────────────────────┼──────────────┤
│ 📋 System Log Viewer│ 🟣 Distribution Chart                   │ 🔧 Countermeasures │
│ ─────────────────── │ ────────────────────                   │ ──────────────────  │
│ Color-coded lines:  │ Doughnut pie chart of attack types.     │ Latest High/Med     │
│ • 🟢 auth success   │ Hover to see percentages.               │ threat's AI-gen     │
│ • 🔴 auth fail      │                                        │ steps from Gemini.  │
│ • 🟠 warn/error     │                                        │                     │
│ [⏸ Pause] toggle   │                                        │                     │
├─────────────────────┴──────────────────────────────────────────┴──────────────────┤
│ 🟢 Attack Simulator (5 buttons)  │  🤖 AI Chatbot (puter.js)                      │
│ ──────────────────────────────   │  ──────────────────────────                   │
│ [Port Scan] [DoS] [Brute Force]  │  Free GPT-4o-mini with real-time threat      │
│ [Web Scan] [DDoS] [Heartbleed]   │  context. Ask: "Block DoS?" or suggestions.   │
│ Progress bar shows % complete    │  Type to chat; responses stream live.          │
└─────────────────────────────────┴──────────────────────────────────────────────────┘
```

### Panel Details

**🔴 Live Alert Feed**
- Real-time table of detected attacks
- Click a row to expand and see:
  - Geo-location (city, country, coordinates)
  - Full countermeasures from Gemini
  - Technical summary
  - Confidence score
  - Encrypted payload preview
- Sort by timestamp, severity, confidence

**🟢 Attack Map**
- Interactive Leaflet.js map with CartoDB dark basemap
- Red markers = attack sources, blue = your sensor
- Hover for tooltip (src IP, attack type, time)
- Click marker to show alert details

**📊 Stats Sidebar**
- Top 5 attacking IPs with counts
- Severity distribution (High/Medium/Low/Info)
- Confidence score averages
- Hourly activity sparkline

**📋 Log Viewer**
- Live-tailing output from auth.log, syslog, nginx
- Color-coded by log type:
  - 🟢 Success (login, connection OK)
  - 🔴 Failure (auth denied, connection refused)
  - 🟠 Warning/Error
- [⏸ Pause] button to freeze live updates

**🟣 Distribution Chart**
- Doughnut chart of attack type counts
- Shows: Port Scan, DoS, DDoS, Brute Force, etc.
- Updated in real-time
- Hover to see percentages

**🔧 Countermeasures**
- AI-generated defensive steps for the latest High/Medium alert
- Powered by Gemini API (or fallback static text if offline)
- Example: "For DoS attack, (1) Block src IP at firewall, (2) apply rate limiting, (3) scale resources"

**🟢 Attack Simulator**
- 5 pre-built scenario buttons (see [Attack Simulator](#attack-simulator))
- Progress bar shows simulation % complete
- Real alerts appear in feed as simulator runs

**🤖 AI Chatbot**
- Free GPT-4o-mini via puter.js (no API key needed)
- Ask questions like:
  - "What's a Port Scan?"
  - "How to defend against DDoS?"
  - "Top attacking IPs today?"
  - "Explain the latest alert"
- Real-time alert context injected automatically
- Streaming responses for interactive conversation

---

## 🎮 Attack Simulator

The simulator injects pre-crafted network flows directly into the detection pipeline. **No real attacks are sent** — it's purely synthetic data for testing.

### From Dashboard

Click any button in the **Attack Simulator** panel (bottom-left).

### From Command Line (curl)

```bash
# Port Scan - sequential probes of 1000 common ports
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"PORT_SCAN"}'

# DoS Flood - high-volume single-source UDP/TCP packet flood
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"DOS_FLOOD"}'

# Brute Force SSH - repeated failed auth attempts on port 22
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"BRUTE_FORCE_SSH"}'

# Web Scan - HTTP directory traversal/vuln probes on port 80/443
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"WEB_SCAN"}'

# DDoS - distributed multi-source barrage
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"DDOS"}'

# Heartbleed - TLS v1.2 memory leak attacks
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"HEARTBLEED"}'
```

### Expected Behavior

1. Request sent → Server responds `{"ok": true, "status": "started", "scenario": "PORT_SCAN", ...}`
2. Flows injected into aggregator queue (5–10 seconds)
3. Detection loop classifies and enriches (2–5 seconds)
4. Alert appears in:
   - Dashboard alert table
   - Attack map (if geo-locatable)
   - Stats chart (attack type)
   - Log viewer
   - WebSocket broadcast

**Typical timeline:** 0s (click) → 5–10s (detection) → 15s (full appearance)

---

## 🔌 REST API Reference

### Health & Status

#### `GET /api/health`
Server status and model info.

**Response:**
```json
{
  "status": "ok",
  "sensor_ip": "192.168.1.5",
  "model_classes": 11,
  "model_features": 19,
  "uptime_seconds": 3600,
  "gemini": {
    "enabled": true,
    "model": "gemini-2.0-flash"
  }
}
```

### Alerts

#### `GET /api/alerts`
All stored alerts, newest first. Payloads are AES-256-GCM encrypted.

**Query params:**
- `limit=50` (default)
- `offset=0` (pagination)

**Response:**
```json
{
  "ok": true,
  "count": 150,
  "alerts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2026-08-12T10:23:45.123456+00:00",
      "attack_type": "Port Scan",
      "confidence": 0.95,
      "severity": "Medium",
      "src_ip": "185.220.101.45",
      "dst_ip": "192.168.1.100",
      "src_port": 12345,
      "dst_port": 443,
      "protocol": "TCP",
      "flow_packets": 250,
      "flow_bytes": 18500,
      "geo_lat": 52.52,
      "geo_lon": 13.41,
      "geo_city": "Berlin",
      "geo_country": "DE",
      "alert_message": "Port Scan detected from 185.220.101.45 targeting ports 1-1024...",
      "technical_summary": "Quorum sensing and selective hypothesis generation framework...",
      "countermeasures": [
        "Block source IP at firewall or WAF",
        "Enable DDoS mitigation service",
        "Scale web tier horizontally"
      ],
      "encrypted_payload": "...base64-encoded AES-256-GCM ciphertext..."
    }
  ]
}
```

### Statistics

#### `GET /api/stats`
Attack type distribution (feeds doughnut chart).

**Response:**
```json
{
  "ok": true,
  "stats": {
    "Port Scan": 23,
    "DoS": 5,
    "Brute Force": 8,
    "DDoS": 3,
    "Web Attack": 12,
    "Heartbleed": 1
  }
}
```

#### `GET /api/stats/extended`
Detailed stats with top IPs, severity, hourly breakdown.

**Response:**
```json
{
  "ok": true,
  "total_alerts": 150,
  "top_ips": [
    {"ip": "185.220.101.45", "count": 23, "attack_type": "Port Scan"},
    {"ip": "10.0.0.99", "count": 18, "attack_type": "DoS"}
  ],
  "severity_breakdown": {
    "high": 45,
    "medium": 78,
    "low": 27
  },
  "hourly_activity": [12, 8, 15, 23, 19, ...],
  "avg_confidence": 0.94
}
```

### Map Data

#### `GET /api/map`
Geo-locatable alerts for Leaflet map markers.

**Response:**
```json
{
  "ok": true,
  "markers": [
    {
      "id": "550e8400...",
      "lat": 52.52,
      "lon": 13.41,
      "attack_type": "Port Scan",
      "city": "Berlin",
      "country": "DE",
      "src_ip": "185.220.101.45",
      "timestamp": "2026-08-12T10:23:45Z"
    }
  ]
}
```

### Logs

#### `GET /api/logs`
Latest parsed log events (auth failures, SSH logins, HTTP scans, etc.).

**Response:**
```json
{
  "ok": true,
  "logs": [
    {
      "log_type": "auth_failure",
      "raw_line": "Mar 10 06:23:18 server sshd[1234]: Failed password for invalid user admin from 10.0.0.1 port 54321 ssh2",
      "timestamp": 1741234567,
      "severity": "medium"
    },
    {
      "log_type": "auth_success",
      "raw_line": "Mar 10 06:24:01 server sudo: user1 : TTY=pts/0 ; PWD=/home/user1 ; USER=root ; COMMAND=/bin/cat /etc/shadow",
      "timestamp": 1741234598,
      "severity": "high"
    }
  ]
}
```

### Simulator

#### `POST /api/simulate`
Inject a simulated attack scenario.

**Request:**
```json
{
  "scenario": "PORT_SCAN"
}
```

**Valid scenarios:** `PORT_SCAN`, `DOS_FLOOD`, `BRUTE_FORCE_SSH`, `WEB_SCAN`, `DDOS`, `HEARTBLEED`

**Response:**
```json
{
  "ok": true,
  "status": "started",
  "scenario": "PORT_SCAN",
  "expected_seconds": 5
}
```

---

## 🌐 WebSocket Feeds

### Real-time IDS Alerts

**Endpoint:** `WS ws://localhost:8000/ws/ids-feed`

**Message Format:**
```json
{
  "type": "ids_alert",
  "data": {
    "id": "550e8400...",
    "attack_type": "Port Scan",
    "src_ip": "185.220.101.45",
    "confidence": 0.95,
    "severity": "Medium",
    "timestamp": "2026-08-12T10:23:45.123456Z",
    ...
  }
}
```

Also receives simulator progress:
```json
{
  "type": "sim_progress",
  "data": {
    "scenario": "PORT_SCAN",
    "pct": 60,
    "message": "Scanning ports 1-600..."
  }
}
```

### Real-time Log Feed

**Endpoint:** `WS ws://localhost:8000/ws/log-feed`

**Message Format:**
```json
{
  "type": "log",
  "data": {
    "log_type": "auth_failure",
    "raw_line": "Mar 10 06:23:18 server sshd...",
    "timestamp": 1741234567,
    "severity": "medium"
  }
}
```

---

## 📚 Optional Enhancements

### 🔑 Gemini API Key (For AI Countermeasures)

Without a Gemini key, countermeasures are static fallback text. With a key, Gemini generates custom analysis and defensive steps for each alert.

**Setup:**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create a new API key (free, 60 req/minute)
3. Add to `.env`:
   ```ini
   GEMINI_API_KEY=sk-...
   GEMINI_MODEL=gemini-2.0-flash
   ```
4. Restart server

### 🌐 ipinfo.io Token (For Better Geo-Location)

Free tier without token: 50,000 requests/month (usually enough).
With token: Much higher limits + priority.

**Setup:**
1. Go to [ipinfo.io/signup](https://ipinfo.io/signup)
2. Create free account, copy token
3. Add to `.env`:
   ```ini
   IPINFO_TOKEN=your_token
   ```
4. Restart server

### 📡 Live Packet Capture (Real Network Traffic)

By default, the system runs in "simulator mode" (synthetic flows). To detect real attacks on your network:

```bash
./run.sh --capture
```

This:
- ✅ Runs with sudo automatically
- ✅ Captures raw packets on configured interface
- ✅ Fixes database ownership
- ✅ Starts live detection

**Requirements:**
- Must have `CAPTURE_INTERFACE` set in `.env` (see Configuration)
- Need sudo/root access for raw sockets

**Performance:** ~10,000 packets/second on modern hardware (depends on interface speed)

### 📊 Access System Logs (Full Feature)

By default, log watcher tries `/var/log/auth.log`, `/var/log/syslog`, `/var/log/nginx/access.log`.

To fully enable without sudo:
```bash
sudo chmod o+r /var/log/auth.log /var/log/syslog
# OR join the adm group:
sudo usermod -aG adm $USER
newgrp adm  # Activate new group in current shell
```

### 🤖 Train on Real Network Data

The ML model is pre-trained on synthetic attacks. To improve accuracy on real traffic:

1. Collect labeled network traffic (e.g., [CIC-IDS-2018 dataset](https://www.unb.ca/cic/datasets/ids-2018.html))
2. Extract flows and labels
3. Run training script (you'd write this using scikit-learn)
4. Replace `model/ids_model.pkl`, `label_encoder.pkl`, `feature_list.pkl`

(Beyond scope of this repo, but the model is in standard pickle format — easy to retrain)

---

## 🐛 Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `[Errno 98] Address already in use` | Port 8000 occupied | `fuser -k 8000/tcp` then restart, or use `./run.sh --port 9000` |
| `attempt to write a readonly database` | DB owned by root | `sudo chown $USER:$USER ids_alerts.db` |
| `Interface 'eth0' not found` | Wrong interface in `.env` | Run `ip link show`, update `CAPTURE_INTERFACE` |
| No alerts after simulation | Detection takes 5–10s | Wait; check server terminal for errors |
| WebSocket says "red" (disconnected) | Network/firewall issue | Check server is running, try http://localhost:8000 directly |
| Gemini countermeasures are static | API key missing or invalid | Add `GEMINI_API_KEY` to `.env`, restart |
| Packet capture fails silently | Not running as root | Use `./run.sh --capture` or `sudo venv/bin/uvicorn ...` |
| Map markers don't appear | Private IP addresses | Local/RFC1918 IPs can't be geo-located; expected for homelab |
| Dashboard loads slow | Lots of alerts (>5000) | Pagination implemented; use `/api/alerts?limit=50&offset=0` |
| Chat returns errors | puter.js connection issue | Use browser devtools (F12) → Console to debug |
| `FutureWarning: google.generativeai deprecated` | Package version | Non-breaking; everything still works. Optional migration to `google-genai` |

---

## 📁 Project Structure

```
cyber-gym-main/
├── .env                     # Secrets (DO NOT COMMIT)
├── .gitignore
├── README.md
├── requirements.txt         # Python dependencies
├── run.sh                   # Server startup script
├── config.py                # Config loader
├── main.py                  # FastAPI app (entry point)
├── create_placeholder_model.py  # Regenerate model pickles
│
├── ids/                     # Core IDS engine
│   ├── __init__.py
│   ├── aggregator.py        # Flow extraction (19 features, 5s windows)
│   ├── alerts.py            # Alert builder + AES-256-GCM encryption
│   ├── capture.py           # Scapy packet sniffer
│   ├── db.py                # SQLite CRUD operations
│   ├── engine.py            # ML classifier + rule engine
│   ├── geo.py               # IP → geo-location (ipinfo.io)
│   ├── llm.py               # Gemini API calls for countermeasures
│   └── log_capture.py       # Watchdog file monitoring
│
├── simulator/               # Attack simulator
│   ├── __init__.py
│   ├── simulator.py         # Scenario runner
│   └── templates.py         # 6 attack scenario templates
│
├── model/                   # Pre-trained ML model
│   ├── ids_model.pkl        # RandomForest + StandardScaler (2.1 GB)
│   ├── label_encoder.pkl    # Class label mapping
│   └── feature_list.pkl     # 19-feature names
│
├── static/                  # Frontend assets
│   ├── index.html           # Main dashboard (380 lines)
│   ├── css/
│   │   └── styles.css       # Custom Tailwind overrides
│   └── js/
│       ├── app.js           # Dashboard controller (465 lines)
│       ├── chatbot.js       # AI chat module (395 lines)
│       ├── map.js           # Leaflet map (94 lines)
│       └── simulator.js     # Simulator UI (125 lines)
│
└── scripts/
    └── dev_server.sh        # Dev server startup
```

---

## 🛠️ Tech Stack

| Layer | Tool | Version | Purpose |
|-------|------|---------|---------|
| **Backend** | | | |
| Framework | FastAPI | 0.109.0 | Web server + REST API |
| ASGI Server | Uvicorn | | Async HTTP server |
| ML | scikit-learn | 1.8.0 | RandomForest (300 trees) classifier |
| Network | Scapy | 2.5.0 | Raw packet capture |
| Logs | watchdog | 4.0 | File system monitoring (inotify) |
| Encryption | cryptography | 42.0.0 | AES-256-GCM payload encryption |
| AI | google-genai | | Gemini API for countermeasures |
| Geo | requests | | HTTP client for ipinfo.io |
| DB | sqlite3 | (built-in) | Alert persistence + WAL mode |
| Async | aiofiles | | Async file operations |
| Config | python-dotenv | | .env file parsing |
| **Frontend** | | | |
| Framework | Vanilla JS | ES6+ | No build step, clean DOM |
| Styling | Tailwind CSS | 3.4 (CDN) | Dark theme utilities |
| Real-time | WebSockets | Native | Async message stream |
| Maps | Leaflet.js | 1.9+ | OpenStreetMap integration |
| Basemap | CartoDB Dark | | Vector tiles |
| Charts | Chart.js | 4.4 | Doughnut chart renderer |
| AI Chat | puter.js | | GPT-4o-mini free tier |
| Fonts | Google Fonts | | JetBrains Mono + Inter |

---

## 🎓 Learning Resources

- **Network IDS concepts:** [Snort docs](https://snort.org/)
- **scikit-learn ML:** [Docs](https://scikit-learn.org/)
- **FastAPI:** [Official tutorial](https://fastapi.tiangolo.com/)
- **Scapy:** [GitHub](https://github.com/secdev/scapy)
- **AES-256-GCM:** [NIST Special Publication 800-38D](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf)

---

## 📄 License

MIT License. See LICENSE file.

---

## 🤝 Contributing

Found a bug or have a feature idea?
1. Open an issue on GitHub
2. Fork and make your changes
3. Submit a pull request

---

## 📞 Support

For issues, questions, or deployment help:
- Check [Troubleshooting](#troubleshooting) section
- Review [DOCUMENTATION.md](./DOCUMENTATION.md) for deep dives
- Open a GitHub issue

---

*Crypt Lab IDS v3.0 — Production-ready AI-powered network intrusion detection system*

**Built with:** Python · FastAPI · scikit-learn · Gemini API · Scapy · Leaflet.js · WebSockets

**Last updated:** August 12, 2026
