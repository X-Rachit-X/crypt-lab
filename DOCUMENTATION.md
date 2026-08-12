# 🔐 Crypt Lab IDS — Complete Technical Documentation

> **Everything about the project: what it is, how every component works, what every library does, and the complete data flow from raw packet to dashboard alert.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Technology Stack — Every Library Explained](#3-technology-stack--every-library-explained)
4. [Project File Reference](#4-project-file-reference)
5. [How Detection Works — Full Data Flow](#5-how-detection-works--full-data-flow)
6. [The Machine Learning Model](#6-the-machine-learning-model)
7. [The Rule Engine](#7-the-rule-engine)
8. [The 19 Network Flow Features](#8-the-19-network-flow-features)
9. [Gemini AI Integration](#9-gemini-ai-integration)
10. [The Chatbot Module (puter.js)](#10-the-chatbot-module-puterjs)
11. [Log Capture & Pattern Matching](#11-log-capture--pattern-matching)
12. [Alert Storage — AES-256-GCM Encryption](#12-alert-storage--aes-256-gcm-encryption)
13. [Geo-location System](#13-geo-location-system)
14. [Telegram Notifications](#14-telegram-notifications)
15. [The Attack Simulator](#15-the-attack-simulator)
16. [REST API Reference](#16-rest-api-reference)
17. [WebSocket Feeds](#17-websocket-feeds)
18. [Frontend Architecture](#18-frontend-architecture)
19. [Statistics Dashboard](#19-statistics-dashboard)
20. [Configuration Reference (.env)](#20-configuration-reference-env)
21. [Database Schema](#21-database-schema)
22. [Setup & Installation](#22-setup--installation)
23. [Security Considerations](#23-security-considerations)
24. [Known Limitations](#24-known-limitations)

---

## 1. Project Overview

Crypt Lab IDS is a **real-time Intrusion Detection System** that monitors a Linux machine's network traffic and system logs, classifies attacks using machine learning, enriches alerts with AI-generated explanations, and presents everything in a live web dashboard.

### What it does

| Capability | How |
|---|---|
| Captures raw network packets | Scapy sniffs on the configured NIC in promiscuous mode |
| Groups packets into flows | 5-tuple flow aggregator with 4-second timeout |
| Extracts 19 statistical features | numpy-based calculation per flow |
| Classifies attack type | Rule engine first, then RandomForest ML model |
| Enriches High-severity alerts | Google Gemini API generates human-readable explanation |
| Watches system logs | Watchdog tails auth.log, syslog, kern.log, nginx access.log |
| Stores alerts securely | SQLite database, payloads encrypted with AES-256-GCM |
| Geolocates attackers | ipinfo.io API lookup cached for 1 hour |
| Sends push notifications | Telegram Bot API for High/Medium alerts |
| Serves a live dashboard | FastAPI + WebSocket push, no polling |
| Plots attack origins on map | Leaflet.js with CartoDB dark tiles |
| Provides an AI chatbot | puter.js powered, GPT-4o-mini, zero API key needed |
| Simulates attacks | 6 pre-built attack scenarios for testing |
| Shows a statistics panel | Top IPs, hourly sparkline, attack type breakdown |

### What it does NOT do

- It does not block traffic (IDS, not IPS). It alerts only.
- It does not decrypt HTTPS/TLS traffic.
- It does not use a packet capture library that requires writing to disk — everything is in-memory.

---

## 2. Architecture DiagramRun

```
                         ┌─────────────────────────────────────────────────────┐
                         │                LINUX HOST MACHINE                   │
                         │                                                     │
  Network Interface      │  ids/capture.py         ids/aggregator.py           │
  (wlo1 / eth0)  ───────►│  Scapy sniff()    ────► FlowAggregator             │
                         │  every IP packet         groups by 5-tuple          │
                         │                          4s timeout → feature vec   │
                         │                                │                    │
                         │  /var/log/auth.log             ▼                    │
                         │  /var/log/syslog    ids/engine.py                   │
                         │  /var/log/kern.log  Rule Engine → ML Model          │
                         │  nginx/access.log   ids_model.pkl → attack_type     │
                         │       │                   │                         │
                         │  ids/log_capture.py        │                        │
                         │  Watchdog file tail        │                        │
                         │       │              asyncio Queue                  │
                         │       │                   │                         │
                         │       └──────────────────►│                         │
                         │                           ▼                         │
                         │               main.py detection_loop()              │
                         │                     │                               │
                         │          ┌──────────┼──────────┐                   │
                         │          ▼          ▼          ▼                   │
                         │      ids/geo.py ids/llm.py ids/alerts.py           │
                         │      ipinfo.io  Gemini API  AES-256-GCM            │
                         │          │          │          │                   │
                         │          └──────────┴──────────┘                   │
                         │                     │                               │
                         │               ids/db.py                             │
                         │               SQLite store                          │
                         │               ids/notify.py                         │
                         │               Telegram push                         │
                         │                     │                               │
                         │               WebSocket broadcast                   │
                         │               /ws/ids-feed                          │
                         └──────────────────────│────────────────────────────┘
                                                │
                         ┌──────────────────────▼────────────────────────────┐
                         │                  BROWSER                           │
                         │                                                    │
                         │  static/index.html  (Tailwind dark grid)           │
                         │  static/js/app.js   (dashboard controller)         │
                         │  static/js/map.js   (Leaflet attack map)           │
                         │  static/js/simulator.js (attack simulator UI)      │
                         │  static/js/chatbot.js   (puter.js AI chatbot)      │
                         │                                                    │
                         └────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack — Every Library Explained

### Backend Python Libraries

#### `fastapi` (v0.115+)
The web framework. Handles all HTTP routes and WebSocket connections. FastAPI uses Python type hints to auto-generate request/response validation. We use it because it natively supports `async/await` — critical for managing WebSocket connections without blocking the detection loop.

Key features used:
- `@app.get()` / `@app.post()` / `@app.delete()` — REST endpoints
- `@app.websocket()` — WebSocket endpoints for live push
- `@app.on_event("startup")` — lifespan handler to start background threads
- `StaticFiles` — serves the `static/` folder at `/static/`
- `FileResponse` — serves `index.html`, `debug.html`

#### `uvicorn` (v0.30+)
The ASGI web server that runs FastAPI. Handles the HTTP/WebSocket protocol layer. Started with `./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000`. Uses `uvloop` on Linux for a faster event loop.

#### `scapy` (v2.5+)
The packet capture and manipulation library. Used in `ids/capture.py` to:
- Sniff raw packets on a named network interface
- Extract IP layer (source IP, dest IP, protocol)
- Extract TCP layer (ports, SYN/FIN/RST/PSH/ACK/URG flags, window size)
- Determine packet size

Requires **root or `CAP_NET_RAW`** privilege to open a raw socket. Run with `sudo` or `sudo setcap cap_net_raw+eip /path/to/python`.

#### `scikit-learn` (v1.8+)
Machine learning library. The trained model is a `Pipeline` containing:
1. `StandardScaler` — normalises all 19 features to mean=0, std=1
2. `RandomForestClassifier(n_estimators=300)` — 300 decision trees, majority-vote classification

Loaded via `joblib.load()` from the `.pkl` files. `predict()` returns the class index, `predict_proba()` returns the probability distribution across all 11 classes.

#### `joblib` (part of scikit-learn)
Serializes/deserializes Python objects efficiently. Used to save and load the three model files:
- `ids_model.pkl` — the full Pipeline object
- `label_encoder.pkl` — maps indices to attack type names
- `feature_list.pkl` — the ordered list of 19 feature names

#### `numpy` (v2.0+)
Numerical computing library. Used throughout:
- `ids/aggregator.py` — builds the 19-element float32 array per flow
- `ids/engine.py` — reshapes the vector for `predict()`, calls `np.nan_to_num()`
- `simulator/templates.py` — defines pre-built feature vectors as `np.array()`

#### `google-genai` (v1.0+)
The **new** Google Generative AI SDK (replaces deprecated `google-generativeai`). Used in `ids/llm.py` and `main.py` for:
- Alert enrichment: `client.models.generate_content(model="gemini-2.0-flash", contents=prompt)`
- Model listing: `client.models.list()`
- Terminal log analysis: `/api/analyze` endpoint

The new SDK automatically reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from environment — no `genai.configure()` needed.

#### `cryptography` (v42+)
Python cryptographic primitives. Used in `ids/alerts.py` for AES-256-GCM encryption:
- `from cryptography.hazmat.primitives.ciphers.aead import AESGCM`
- `AESGCM(key).encrypt(nonce, plaintext, None)` — authenticated encryption
- The 32-byte key comes from `IDS_AES_KEY` env var (64 hex chars)
- 12-byte random nonce prepended to ciphertext, whole thing base64-encoded

#### `requests` (v2.31+)
HTTP client for synchronous requests. Used in:
- `ids/geo.py` — calls `ipinfo.io/{ip}` for geolocation
- `ids/notify.py` — calls Telegram Bot API `sendMessage`

#### `psutil` (v6+)
System process utilities. Used in `main.py` to gather system metrics (CPU, memory) for the `/api/system-info` endpoint.

#### `watchdog` (v4+)
File system monitoring library. Used in `ids/log_capture.py` to efficiently watch log files for new lines — avoids polling, uses inotify on Linux.

#### `python-dotenv` (v1.0+)
Loads `.env` file into environment variables at startup. Used in `config.py` via `load_dotenv()`. This keeps secrets (API keys, AES key) out of source code.

#### `aiofiles`
Async file I/O. Used for non-blocking reads in some log capture paths.

#### `sqlalchemy` (listed in requirements) / **direct `sqlite3`**
The actual database layer uses Python's built-in `sqlite3` module with thread-local connections. Each thread gets its own SQLite connection to avoid `check_same_thread` errors.

---

### Frontend Libraries (CDN, no npm)

#### Tailwind CSS (v3, CDN)
Utility-first CSS framework. The entire dashboard is styled with Tailwind classes. No custom CSS framework needed — classes like `bg-zinc-900`, `text-cyan-400`, `flex`, `grid` handle all layout.

#### Leaflet.js (v1.9.4, CDN)
Interactive map library. Used in `static/js/map.js` to:
- Display a dark-themed map (CartoDB Dark Matter tiles)
- Plot attack origin markers as animated pulsing circles
- Show popups with IP, attack type, city, country

#### Chart.js (v4.4, CDN)
Chart rendering library. Used for the doughnut/pie chart showing attack type distribution. `incrementChart(attackType)` updates it live as each alert arrives.

#### puter.js (v2, CDN)
Free frontend AI library. Powers the chatbot at zero cost. Key facts:
- No API key required — users authenticate via `puter.com` (free account)
- `puter.ai.chat(messages, { model: 'gpt-4o-mini', stream: true })` — streaming AI
- 400+ models available; we use `gpt-4o-mini` for speed + capability
- "User-Pays" model — the authenticated user's puter credits are consumed
- Loads via `<script src="https://js.puter.com/v2/"></script>`

#### Lucide Icons
SVG icon set used for the shield/lock icon in the header. Loaded inline as SVG.

---

## 4. Project File Reference

```
cyber-gym-main/
│
├── main.py                 ← FastAPI application (1345 lines)
│                             All HTTP endpoints, WebSocket handlers,
│                             detection loop, startup lifecycle
│
├── config.py               ← Settings dataclass, loads .env via python-dotenv
│
├── requirements.txt        ← All Python dependencies with pinned versions
│
├── run.sh                  ← Helper startup script (checks deps, kills port 8000,
│                             activates venv, starts uvicorn)
│
├── simulate.sh             ← Quick script to fire a simulated attack
│
├── create_placeholder_model.py  ← Generates dummy .pkl files for testing
│                                   without a real trained model
│
├── .env                    ← Environment variables (secrets, never committed)
│
├── ids_alerts.db           ← SQLite database (auto-created on first run)
│
├── ids/                    ← IDS engine package
│   ├── __init__.py         ← Exports _recent_log_lines deque
│   ├── capture.py          ← Scapy packet sniffer
│   ├── aggregator.py       ← Flow aggregator + 19-feature extractor
│   ├── engine.py           ← Rule engine + ML classifier
│   ├── llm.py              ← Gemini AI alert enrichment (rate-limited, cached)
│   ├── geo.py              ← ipinfo.io geolocation with 1h cache
│   ├── alerts.py           ← Alert builder + AES-256-GCM encryption
│   ├── db.py               ← SQLite CRUD + stats queries
│   ├── log_capture.py      ← Watchdog log file monitor + pattern matching
│   └── notify.py           ← Telegram Bot notifications
│
├── model/                  ← ML model artifacts
│   ├── ids_model.pkl       ← Trained Pipeline (StandardScaler + RandomForest)
│   ├── label_encoder.pkl   ← LabelEncoder (index → attack type name)
│   └── feature_list.pkl    ← List of 19 feature names in order
│
├── simulator/              ← Attack simulation package
│   ├── __init__.py
│   ├── simulator.py        ← Runs a scenario: injects flows + log lines
│   └── templates.py        ← 6 pre-built attack scenario definitions
│
├── static/                 ← Frontend assets served by FastAPI
│   ├── index.html          ← Main dashboard (Tailwind dark theme, 3-column grid)
│   ├── debug.html          ← Debug panel (Gemini call monitor)
│   ├── vm_config.html      ← VM config editor UI
│   ├── css/styles.css      ← Additional CSS
│   └── js/
│       ├── app.js          ← Dashboard controller (WebSocket, alert table,
│       │                     chart, log viewer, stats panel)
│       ├── map.js          ← Leaflet attack map
│       ├── simulator.js    ← Simulator panel UI
│       └── chatbot.js      ← puter.js chatbot (open/close, context,
│                             streaming responses, IP click-to-ask)
│
└── files/                  ← Developer reference docs (Markdown)
    ├── 01_model_overview.md
    ├── 02_loading_the_model.md
    ├── 03_features_reference.md
    ├── 04_running_inference.md
    ├── 05_live_packet_capture.md
    ├── 06_error_handling.md
    └── 07_quick_reference.md
```

---

## 5. How Detection Works — Full Data Flow

This is the complete journey from a raw TCP packet to a notification on your phone.

### Step 1 — Packet Capture (`ids/capture.py`)

```
Network NIC (e.g. wlo1)
        │
        ▼ (promiscuous mode)
Scapy sniff(iface="wlo1", prn=_process_packet, store=False)
        │
        ▼
_process_packet(pkt):
  - Extract IP layer: src_ip, dst_ip, proto
  - Extract TCP layer: ports, SYN/FIN/RST/PSH/ACK/URG flags
  - Determine direction: src_ip in local_ips → "fwd", else "bwd"
  - Call aggregator.add_packet(pkt_info dict)
```

Every IP packet on the interface is captured. `store=False` means Scapy does not buffer them — they're processed and discarded immediately, keeping memory usage flat.

### Step 2 — Flow Aggregation (`ids/aggregator.py`)

```
aggregator.add_packet(pkt)
  │
  ▼
Flow key = (src_ip, dst_ip, src_port, dst_port, proto)
  │
  ├── New key? → create new flow list
  └── Existing key? → append packet to flow list
        │
        ▼
_reaper thread (runs every 1s):
  For each flow last seen > 4 seconds ago:
    - Pop it from the flows dict
    - Call _finalize_flow(key, packets)
          │
          ▼
    _compute_features(packets) → 19-element numpy float32 array
          │
          ▼
    Push { "source": "flow", "features": vec, "meta": { src_ip, ... } }
    into asyncio detection_queue via loop.call_soon_threadsafe()
```

The 4-second timeout (`FLOW_TIMEOUT = 4.0`) is aggressive by design — it catches fast attacks like port scans and DoS bursts very quickly without waiting for the TCP FIN.

### Step 3 — Feature Extraction

The `_compute_features()` method processes the list of raw packet dicts and computes exactly 19 statistical metrics. See [Section 8](#8-the-19-network-flow-features) for the full list.

### Step 4 — Classification (`ids/engine.py`)

```
detection_queue.get() → feature_vector (numpy array, shape [19])
      │
      ▼
ids/engine.py classify(feature_vec):
      │
      ├─── RULE ENGINE (fast path, checked first)
      │    If fwd_pps > 10000          → DDoS/DoS
      │    If rst > 50 AND pps > 500   → Brute Force
      │    If rst > 30 AND pkt < 120   → Port Scan
      │    If syn > 100 AND ack < 20   → DoS
      │    If pkt_mean > 1500 AND urg  → Heartbleed
      │    If bytes_ps > 5MB/s         → DDoS
      │
      └─── ML ENGINE (if no rule matched)
           pipeline.predict(X)          → class index
           pipeline.predict_proba(X)    → confidence per class
           le.inverse_transform(pred)   → attack type string
                │
                └─── Second-opinion check:
                     If ML says "Benign" with < 80% confidence
                     AND any attack class has ≥ 20% probability
                     → use that attack class instead
```

### Step 5 — Detection Loop (`main.py`)

```python
async def detection_loop():
    while True:
        event = await detection_queue.get()
        features = event["features"]
        meta     = event["meta"]

        result = ids_engine.classify(features)

        if not result["is_attack"]:
            continue  # Benign traffic — ignore

        # Dedup: skip if same src_ip + attack_type seen < 3s ago
        key = (meta["src_ip"], result["label"])
        if key in recent_detections and time.time() - recent_detections[key] < 3.0:
            continue
        recent_detections[key] = time.time()

        # Geo lookup (cached 1h)
        geo  = await asyncio.to_thread(ids_geo.lookup, meta["src_ip"], IPINFO_TOKEN)

        # LLM enrichment (High severity only, rate-limited, cached)
        severity = ids_alerts.get_severity(result["label"])
        if severity == "High":
            llm = await ids_llm.enrich(context)
        else:
            llm = ids_llm.get_static_response(result["label"])

        # Build full alert dict
        alert = ids_alerts.build_alert(result, geo, llm, meta)

        # Encrypt & store
        encrypted = ids_alerts.encrypt_alert(alert)
        ids_db.store_alert(alert, encrypted)

        # Telegram notification
        ids_notify.notify(alert, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

        # Broadcast to all connected WebSocket clients
        await broadcast_alert(alert)
```

### Step 6 — WebSocket Broadcast

```
broadcast_alert(alert)
      │
      ▼
For every WebSocket in active_connections["vm1"] + active_connections["vm2"]:
  await ws.send_text(json.dumps({"type": "ids_alert", "data": alert}))
      │
      ▼
Browser → app.js WebSocket onmessage handler
  → addAlertRow(alert)        adds row to alert table
  → attackMap.addMarker(alert) plots on Leaflet map
  → incrementChart(attack_type) updates doughnut chart
  → chatbot.notifyNewAlert(alert) shows red notification dot
```

---

## 6. The Machine Learning Model

### Training Dataset
The model was trained on the **CIC-IDS2017** dataset (Canadian Institute for Cybersecurity). This dataset contains:
- ~2.8 million network flows
- 80% Benign traffic
- 20% Attack traffic across 14 categories
- Features extracted using CICFlowMeter

### Model Architecture
```
Pipeline:
  Step 1: StandardScaler
    - Normalizes each of the 19 features to mean=0, std=1
    - Prevents features with large ranges (e.g. bytes_per_s) from dominating
    - Parameters learned during training are saved in the .pkl file

  Step 2: RandomForestClassifier(n_estimators=300)
    - 300 decision trees, each trained on a random subset of training data
    - Each tree votes on the class; majority wins
    - predict_proba() returns the fraction of trees voting for each class
    - More trees = more stable but slower inference
```

### Classes (11)
```
Benign, Brute Force, Bot, DDoS, DoS, DoS GoldenEye,
DoS Hulk, DoS slowloris, Heartbleed, Infiltration,
Port Scan, Web Attack, FTP-Patator, SSH-Patator
```
(Exact class names depend on the training run — the `label_encoder.pkl` is authoritative.)

### Class Imbalance Problem & The Second-Opinion Fix
CIC-IDS2017 is ~80% Benign. This means the model learns a bias toward predicting "Benign" — it's statistically safer to say Benign when unsure. The second-opinion check corrects this:

```python
if label == "Benign" and conf < 0.80:
    attack_probs = { k: v for k, v in all_probs.items() if k != "Benign" }
    best_attack = max(attack_probs, key=attack_probs.get)
    if attack_probs[best_attack] >= 0.20:
        return { "label": best_attack, ... }  # Override to attack class
```

This catches cases where the model is "uncertain Benign" (60-79%) but has a 20%+ signal for a real attack type.

### Model Files
| File | Contents | Size |
|---|---|---|
| `model/ids_model.pkl` | Full Pipeline object (StandardScaler + RandomForest) | ~50-200 MB |
| `model/label_encoder.pkl` | LabelEncoder mapping index → class name | tiny |
| `model/feature_list.pkl` | List of 19 feature names in order | tiny |

---

## 7. The Rule Engine

Before calling the ML model, `ids/engine.py` runs a fast rule-based check. Rules are ordered by priority and are based on known statistical signatures from CIC-IDS2017.

| Rule | Condition | Detected As |
|---|---|---|
| **DDoS flood** | `fwd_pps > 10000` AND `bwd_pkts > 10` | DDoS |
| **DoS flood** | `fwd_pps > 10000` AND `bwd_pkts <= 10` | DoS |
| **Brute Force** | `rst_count > 50` AND `fwd_pps > 500` AND `fwd_pkts > 100` | Brute Force |
| **Port Scan** | `rst_count > 30` AND `fwd_pkts > 100` AND `pkt_mean < 120` | Port Scan |
| **SYN Flood** | `syn_count > 100` AND `ack_count < 20` AND `rst_count < 30` | DoS |
| **Port Scan fallback** | `fwd_pkts > 200` AND `pkt_mean < 80` AND `bwd_pkts < 10` | Port Scan |
| **Heartbleed** | `pkt_mean > 1500` AND `urg_count > 1` | Heartbleed |
| **High-BW DDoS** | `bytes_per_s > 5,000,000` | DDoS |

Why rules first? The ML model has a ~50ms inference time. Rules run in microseconds and catch the most common, obvious attacks with high confidence. The ML model handles everything else.

---

## 8. The 19 Network Flow Features

These are the exact features extracted per flow in `ids/aggregator.py`. The order is permanent — changing it would break compatibility with the trained model.

| Index | Feature Name | Unit | Description |
|---|---|---|---|
| 0 | `flow_duration` | seconds | Total duration of the flow |
| 1 | `total_fwd_packets` | count | Packets sent FROM the source IP |
| 2 | `total_bwd_packets` | count | Packets sent TO the source IP (responses) |
| 3 | `flow_bytes_per_s` | bytes/s | Total bytes ÷ flow duration |
| 4 | `flow_packets_per_s` | pkts/s | Total packets ÷ flow duration |
| 5 | `packet_length_mean` | bytes | Average packet size |
| 6 | `packet_length_std` | bytes | Standard deviation of packet sizes |
| 7 | `packet_length_variance` | bytes² | Variance of packet sizes |
| 8 | `syn_flag_count` | count | Number of packets with SYN flag |
| 9 | `ack_flag_count` | count | Number of packets with ACK flag |
| 10 | `rst_flag_count` | count | Number of packets with RST flag |
| 11 | `psh_flag_count` | count | Number of packets with PSH flag |
| 12 | `urg_flag_count` | count | Number of packets with URG flag |
| 13 | `average_packet_size` | bytes | Same as packet_length_mean (duplicate for model compat) |
| 14 | `down_per_up_ratio` | ratio | bwd_bytes ÷ fwd_bytes (response ratio) |
| 15 | `fwd_packets_per_s` | pkts/s | Forward packets per second |
| 16 | `bwd_packets_per_s` | pkts/s | Backward packets per second |
| 17 | `active_mean` | seconds | Mean active time (placeholder — 0.0) |
| 18 | `idle_mean` | seconds | Mean idle time (placeholder — 0.0) |

### Attack Signatures in Feature Space

| Attack | Key features | Why |
|---|---|---|
| **Port Scan** | Low `pkt_mean` (~50 bytes), high `rst_count`, low `down_per_up_ratio` | SYN probes are tiny; closed ports return RST; no real data exchanged |
| **Brute Force** | High `rst_count` + `fwd_pps > 500` + larger `pkt_mean` (~80 bytes) | Each auth attempt = slightly bigger packets than pure SYN scan |
| **DoS/SYN Flood** | Very high `syn_count`, almost no `ack_count`, extreme `fwd_pps` | Flood of SYNs with no corresponding ACKs |
| **DDoS** | Same as DoS but `bwd_pkts > 10` (distributed — server still responding to some) | Multiple sources means some get through |
| **Heartbleed** | Large `pkt_mean > 1500`, URG flag set | Malformed heartbeat = oversized TLS record |
| **Web Attack** | Log-based only (HTTP 4xx burst) — no reliable flow signature | Detected via log pattern, not flow features |

---

## 9. Gemini AI Integration

### Role in the System
Gemini is a **post-detection enricher**. It does NOT detect attacks. After the rule engine or ML model classifies traffic as an attack, Gemini is called to generate human-readable context.

### When Gemini is Called
- **High severity alerts only** (DoS, DDoS, Bot, Heartbleed, Infiltration)
- Medium and Low severity use static pre-written countermeasures (no API call)
- Rate-limited to 10 calls per minute (token bucket algorithm)
- Cached: same `(attack_type, src_ip)` pair within 60 seconds → returns cached result
- If API key is missing or call fails → falls back to `_build_fallback()` deterministic response

### What Gemini Returns (JSON)
```json
{
  "alert_message": "One sentence summary for non-technical admin",
  "technical_summary": "2-3 sentences for security analyst",
  "countermeasures": [
    "Immediate action 1",
    "Immediate action 2",
    "Preventive action 3",
    "Monitoring action 4"
  ],
  "threat_level_explanation": "One sentence explaining the severity"
}
```

### The Prompt Template
The prompt includes:
- Attack type and source IP
- Geo-location (city, country)
- Confidence percentage and severity
- Traffic statistics (packets/s, bytes/s, SYN count, packet size)
- Related log events from `_recent_log_lines`

### API SDK
Uses `google-genai` (new SDK, 2025):
```python
from google import genai
client = genai.Client()  # reads GEMINI_API_KEY from env automatically
resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
```

### Manual Log Analysis
The `/api/analyze` endpoint lets you manually send terminal logs to Gemini:
- Accepts `{ "logs": [...] }` in POST body
- Tries the configured model, then falls back through alternatives
- Returns `security_analysis`, `attack_detection[]`, `recommendations[]`

---

## 10. The Chatbot Module (puter.js)

### What It Is
A floating AI chatbot panel on the dashboard powered by puter.js. Uses GPT-4o-mini via puter's free service. No API key required, no backend changes.

### Architecture
```
User types question
       │
       ▼
chatbot.js (runs entirely in browser)
       │
       ├── fetchSystemContext()
       │     GET /api/alerts  → last 20 alerts
       │     GET /api/stats   → attack counts
       │     GET /api/logs    → last 30 log lines
       │
       ├── buildSystemPrompt(context)
       │     Injects real alert data into system message
       │
       └── puter.ai.chat(messages, { model: "gpt-4o-mini", stream: true })
               │
               ▼
         GPT-4o-mini responds with knowledge of YOUR actual alerts
               │
               ▼
         Streamed word-by-word into the chat bubble
```

### Key Files
- `static/js/chatbot.js` — all logic (395 lines)
- `static/index.html` — toggle button, panel HTML, CSS, puter.js script tag

### Features
| Feature | Implementation |
|---|---|
| Floating panel, bottom-right | Fixed CSS positioning, 420×560px |
| Streaming responses | `for await (const part of response)` loop |
| Live context injection | Fetches alerts/stats/logs on open, refreshes every 60s |
| 6 quick-action buttons | Pre-built questions rendered from `QUICK_ACTIONS` array |
| IP click-to-ask | Every IP in alert table has click handler → `chatbot.askAboutIP(ip)` |
| New alert notifications | Red dot on toggle button via `notifyNewAlert(alert)` |
| Conversation history | Last 20 messages maintained in memory |
| Context staleness check | If context > 60s old, refetches before answering |

### The System Prompt
The chatbot always sends the full current state as its system prompt:
```
You are the AI security analyst for "Crypt Lab"...

ATTACK STATISTICS: Port Scan: 3, Brute Force: 12...

RECENT ALERTS:
[2026-03-10T14:22:00] Brute Force from 218.92.0.1 (Shanghai, CN) Severity:Medium...

RECENT SYSTEM LOGS:
[auth_failure] Failed password for root from 218.92.0.1 port 54000...
```

This means the AI answers questions using your actual real data, not generic security advice.

### First-Time Setup
puter.js requires a free `puter.com` account on first use. The sign-in popup appears automatically. After that, the AI works indefinitely.

---

## 11. Log Capture & Pattern Matching

### Watched Files (configurable in `.env`)
```
LOG_PATHS=/var/log/auth.log,/var/log/syslog,/var/log/kern.log,/var/log/nginx/access.log
```

### How It Works
`ids/log_capture.py` uses a Watchdog `FileSystemEventHandler` to detect when a log file grows. When new bytes arrive:
1. Seeks to the last known position
2. Reads new lines
3. Applies noise filter (skips irrelevant system noise)
4. Applies attack patterns (regex matching)
5. Extracts IP address from matched lines
6. Pushes log event to the detection queue

### Noise Filter
Lines containing any of these strings are silently dropped:
```
wpa_supplicant, CTRL-EVENT-*, CRON[, snap.*, NetworkManager,
systemd-resolved, dbus-daemon, bluetoothd, avahi-daemon, ...
```
This eliminates WiFi reconnection events, cron job logs, browser snap packages, etc.

### Attack Patterns (Regex)
| Pattern | Type | Severity |
|---|---|---|
| `Failed password` | auth_failure | High |
| `Invalid user .* from` | auth_failure | High |
| `POSSIBLE BREAK-IN ATTEMPT` | auth_failure | High |
| `too many authentication failures` | auth_failure | High |
| `sudo:.* NOT in sudoers` | privilege_escalation | High |
| `sudo:.* incorrect password attempt` | privilege_escalation | High |
| `apparmor="DENIED" operation="exec\|ptrace\|mount"` | privilege_escalation | Medium |
| `kernel:.* SYN.*flood` | auth_failure | High |
| `kernel:.* nf_conntrack.*table full` | auth_failure | High |
| `HTTP 400/401/403/404/405/429` | http_scan | Medium |
| `Accepted password\|publickey` | ssh_success | Low |

### HTTP Burst Detection
In addition to per-line matching, a sliding window detects HTTP 404 bursts:
- More than 10 non-200 HTTP responses from the same IP within 30 seconds → `Web Attack` alert
- This catches directory enumeration tools (DirBuster, ffuf, gobuster)

### Log Rotation Handling
When a log file is replaced (rotation), the watcher detects the inode change and resets its file position to 0 to read the new file from the beginning.

### _recent_log_lines
A `collections.deque(maxlen=50)` shared between `log_capture.py` and `main.py`. Used to inject relevant log context into Gemini prompts — the AI sees real log lines related to each attack.

---

## 12. Alert Storage — AES-256-GCM Encryption

### Why Encryption?
Alert data contains IP addresses, attack details, and network topology information. Encrypting stored payloads means even if the SQLite database file is exfiltrated, the detailed payload is unreadable without the key.

### How It Works (`ids/alerts.py`)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

key   = bytes.fromhex(IDS_AES_KEY)   # 32 bytes (256 bits)
nonce = os.urandom(12)               # 12 bytes random nonce (96 bits, standard for GCM)
plain = json.dumps(alert).encode()   # full alert dict → UTF-8 bytes
ct    = AESGCM(key).encrypt(nonce, plain, None)  # authenticated encryption
token = base64.b64encode(nonce + ct)  # prepend nonce, base64-encode
```

### AES-256-GCM Properties
- **256-bit key** — quantum-resistant for the foreseeable future
- **GCM (Galois/Counter Mode)** — provides both confidentiality AND integrity
- **12-byte random nonce** — ensures every encryption is unique even for identical payloads
- **No additional authenticated data** — `None` passed as AAD parameter
- **Authentication tag** — GCM appends a 16-byte MAC; decryption fails if the ciphertext is tampered with

### Key Generation
```bash
python3 -c "import os; print(os.urandom(32).hex())"
# Paste result into .env as IDS_AES_KEY=<64 hex chars>
```

### Database Storage
The `encrypted_payload` column stores the base64 token. The other columns (IP, attack type, timestamp) are stored in plaintext for querying — only the full detail payload is encrypted.

### Deduplication
`INSERT OR IGNORE` is used — the `id` column (UUID4) is the PRIMARY KEY. Duplicate inserts (from race conditions) are silently ignored.

### Auto-Rotation
On startup, `init_db()` deletes all alerts older than 7 days:
```sql
DELETE FROM alerts WHERE timestamp < datetime('now', '-7 days')
```

---

## 13. Geo-location System

### How It Works (`ids/geo.py`)

1. **Private IP check**: `ipaddress.ip_address(ip).is_private` → returns `{"city": "Local Network", "country": "Internal"}` immediately, no HTTP call
2. **Cache check**: If `(ip, expiry)` in `_cache` and not expired → return cached result
3. **API call**: `GET https://ipinfo.io/{ip}[?token={IPINFO_TOKEN}]`
4. **Parse response**: Extract `loc` (lat,lon), `city`, `region`, `country`, `org`
5. **Cache result** for 1 hour

### Response Format
```python
{
    "ip": "185.220.101.45",
    "lat": 51.5085,
    "lon": -0.1257,
    "city": "London",
    "region": "England",
    "country": "GB",
    "org": "AS205100 F3 Netze e.V."
}
```

### Rate Limits
- Free ipinfo.io: 50,000 requests/month
- With `IPINFO_TOKEN`: 150,000 requests/month
- The 1-hour cache means repeated attacks from the same IP only cost 1 lookup per hour

---

## 14. Telegram Notifications

### Setup
1. Create a bot via `@BotFather` on Telegram
2. Get `TELEGRAM_BOT_TOKEN`
3. Get your `TELEGRAM_CHAT_ID` via `getUpdates`
4. Add both to `.env`

### Behaviour
- Fires for **High** and **Medium** severity alerts only
- Deduplication: same `(src_ip, attack_type)` pair silently skipped for **1 hour**
- Non-blocking: HTTP request runs in a background thread
- Message format includes: attack type, severity, source IP, geo location, timestamp, alert message

### Example Message
```
🚨 HIGH ALERT — Brute Force
From: 218.92.0.1 (Shanghai, CN)
Time: 2026-03-10 14:22:33 UTC
Confidence: 93%

Brute force login attempt detected — credentials under attack.

Crypt Lab IDS
```

---

## 15. The Attack Simulator

### Purpose
Test the IDS without needing real attack traffic. Injects pre-built flow vectors and synthetic log lines directly into the detection pipeline, bypassing Scapy entirely.

### How It Works (`simulator/simulator.py`)
```python
async def run_scenario(scenario_key, aggregator, broadcast_fn):
    scenario = SCENARIOS[scenario_key]

    # Inject each flow directly into the detection queue
    for flow in scenario["flows"]:
        aggregator.inject_flow(flow["features"], flow["meta"])
        await asyncio.sleep(0.5)

    # Inject log lines directly into _recent_log_lines
    for line in scenario["log_lines"]:
        _recent_log_lines.appendleft({"raw_line": line, ...})

    # Broadcast progress updates via WebSocket
    await broadcast_fn({"type": "simulator_progress", "percent": ...})
```

### Scenarios (`simulator/templates.py`)

| Scenario Key | Name | Attack Type | How It Triggers |
|---|---|---|---|
| `PORT_SCAN` | Port Scan | Port Scan | `rst_count=180`, `rst > 30 + pkt_mean < 120` rule |
| `DOS_FLOOD` | DoS Flood | DoS | `syn_count=4980`, `syn > 100 + ack < 20` rule |
| `BRUTE_FORCE_SSH` | Brute Force SSH | Brute Force | `rst_count=400 + fwd_pps=1733`, rule match + 50 SSH log lines |
| `WEB_SCAN` | Web Scan | Web Attack | 50 HTTP 404 log lines → HTTP burst detector |
| `DDOS` | DDoS | DDoS | 5 flows with `bytes_ps=8M > 5MB/s` rule |
| `HEARTBLEED` | Heartbleed | Heartbleed | `pkt_mean=2000 + urg_count=3` rule |

### Starting a Simulation
```bash
# Via API
curl -s -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "PORT_SCAN", "vm_id": "vm1"}'

# Via simulate.sh script
./simulate.sh
```

---

## 16. REST API Reference

All endpoints served by FastAPI on port 8000.

### Alert Endpoints

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/api/alerts` | Last 50 alerts, newest first | `[{id, timestamp, attack_type, src_ip, ...}]` |
| `DELETE` | `/api/alerts/clear` | Delete all alerts from DB | `{"ok": true}` |

### Stats Endpoints

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/api/stats` | Attack type counts | `{"Port Scan": 3, "Brute Force": 12, ...}` |
| `GET` | `/api/stats/extended` | Full stats: top IPs, hourly, severity, attack dist | `{ok, top_ips, hourly, severity, attack_dist}` |
| `GET` | `/api/map` | Alert data for Leaflet markers | `[{src_ip, geo_lat, geo_lon, ...}]` |

### Log Endpoints

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/api/logs` | Last 100 captured log lines | `[{log_type, severity, src_ip, raw_line, ...}]` |
| `DELETE` | `/api/logs/clear` | Clear the in-memory log buffer | `{"ok": true}` |

### Gemini / AI Endpoints

| Method | Path | Description | Response |
|---|---|---|---|
| `POST` | `/api/analyze` | Send logs to Gemini for analysis | `{security_analysis, attack_detection[], recommendations[]}` |
| `GET` | `/api/models` | List available Gemini models | `{ok, models[]}` |

### System Endpoints

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/api/health` | Server health check | `{status, gemini, connections}` |
| `GET` | `/api/system-info` | CPU, memory, uptime | `{cpu, memory, ...}` |
| `POST` | `/api/simulate` | Run attack scenario | `{ok, scenario, ...}` |

### Page Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Main dashboard (`index.html`) |
| `GET` | `/debug` | Debug panel (`debug.html`) |
| `GET` | `/vm-config` | VM config editor |
| `GET` | `/static/*` | Static assets (JS, CSS) |

---

## 17. WebSocket Feeds

### `/ws/ids-feed` (vm_id: vm1 or vm2)

The main alert feed. Every connected browser client receives:

```json
// New alert
{
  "type": "ids_alert",
  "data": {
    "id": "uuid4",
    "timestamp": "2026-03-10T14:22:33+00:00",
    "attack_type": "Brute Force",
    "src_ip": "218.92.0.1",
    "dst_ip": "192.168.1.100",
    "severity": "Medium",
    "confidence": 0.93,
    "geo_lat": 31.2222,
    "geo_lon": 121.4581,
    "geo_city": "Shanghai",
    "geo_country": "CN",
    "alert_message": "Brute force login attempt detected...",
    "technical_summary": "...",
    "countermeasures": ["Block the IP...", "Enable MFA..."],
    "related_logs": ["Failed password for root from 218.92.0.1..."]
  }
}

// Alerts cleared
{ "type": "clear_alerts" }

// Simulator progress
{ "type": "simulator_progress", "percent": 45, "message": "Injecting flows..." }
```

### `/ws/log-feed`

Streams system log lines in real-time:

```json
{
  "type": "log",
  "data": {
    "log_type": "auth_failure",
    "severity": "High",
    "src_ip": "218.92.0.1",
    "raw_line": "Failed password for root from 218.92.0.1 port 54000 ssh2",
    "timestamp": "2026-03-10T14:22:30+00:00"
  }
}
```

### `/ws/debug`

Streams Gemini API call metadata for the debug panel:

```json
{
  "type": "event",
  "data": {
    "ts": 1741617753.4,
    "event": "gemini_call",
    "duration_ms": 843,
    "chars": 1420,
    "model": "gemini-2.0-flash"
  }
}
```

---

## 18. Frontend Architecture

### Dashboard Layout (`static/index.html`)

3-column CSS Grid with Tailwind:
```
┌──────────────────────────┬────────────────┐
│   Live Alert Feed        │  Geo Map       │
│   (col-span-2)           │                │
├──────────┬───────────────┼────────────────┤
│ Log Feed │ Attack Chart  │ Countermeasures│
│          │               │                │
└──────────┴───────────────┴────────────────┘
```

Below: collapsible Statistics Panel (top IPs, hourly sparkline, attack breakdown)

### `static/js/app.js` — Dashboard Controller

| Function | Description |
|---|---|
| `addAlertRow(alert)` | Creates `<tr>` + expandable detail row, inserts at top of table |
| `connectIdsFeed()` | Opens WebSocket, handles auto-reconnect (3s), processes messages |
| `connectLogFeed()` | Opens log WebSocket, appends lines to log viewer |
| `loadInitialData()` | Fetches initial alerts, stats, map, logs on page load |
| `loadExtendedStats()` | Fetches `/api/stats/extended`, renders all 4 stat sections |
| `renderTopIps(topIps)` | Renders IP list with colored progress bars |
| `renderHourly(hourly)` | Builds 24 time slots, renders sparkline bars |
| `renderAttackDist(dist)` | Renders attack type rows with count bars |
| `incrementChart(type)` | Updates doughnut chart live when new alert arrives |
| `updateCountermeasures(alert)` | Updates the countermeasures panel with latest alert's steps |
| `formatTime(ts)` | Formats ISO timestamp to `HH:MM:SS` |
| `escHtml(str)` | HTML-escapes strings before inserting into DOM |

### `static/js/map.js` — Leaflet Map

- Initializes Leaflet map with CartoDB Dark Matter tiles
- `addMarker(alert)`: creates a pulsing `CircleMarker` at the attacker's coordinates
- Popup shows: IP, attack type, geo location, severity, timestamp
- Markers fade after 30 seconds

### `static/js/simulator.js` — Simulator UI

- Renders scenario buttons
- Shows a progress bar during scenario execution
- Displays "Detected: [attack_type]" feedback when the IDS triggers
- Connected to the WebSocket `simulator_progress` event type

### `static/js/chatbot.js` — AI Chatbot

See [Section 10](#10-the-chatbot-module-puterjs) for full details.

---

## 19. Statistics Dashboard

The collapsible stats panel below the main grid provides:

### Severity Badges (Always Visible)
- 🔴 **High**: count from DB
- 🟡 **Medium**: count from DB
- 🔵 **Low**: count from DB

### Top Attacking IPs
- Fetched from `fetch_top_ips(10)` in `ids/db.py`
- Shows IP, hit count, last seen time, attack types
- Colored progress bar (proportional to max IP count)
- Colors: High severity IPs → red bar, Medium → amber, others → cyan

### Hourly Activity (Last 24h)
- Fetched from `fetch_hourly_counts(24)` in `ids/db.py`
- 24 sparkline bars representing each hour
- Bar height proportional to max count in any hour
- Missing hours (no alerts) → zero-height bar

### Attack Type Breakdown
- Fetched from `fetch_stats()` in `ids/db.py`
- Each attack type shown with count and proportional bar
- Color-coded by attack category

### Refresh Strategy
- On page load: `loadInitialData()` calls `loadExtendedStats()`
- On new alert: debounced 5-second refresh (avoids hammering DB during attack)
- On clear alerts: immediate refresh
- Automatic: `setInterval(loadExtendedStats, 60000)` — every 60 seconds

---

## 20. Configuration Reference (.env)

Create `.env` in the project root:

```bash
# ── Gemini AI ──────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash        # or gemini-1.5-flash-latest

# ── IDS Network Capture ────────────────────────────────────────
CAPTURE_INTERFACE=wlo1               # your NIC name (ip link show)
LOG_PATHS=/var/log/auth.log,/var/log/syslog,/var/log/kern.log,/var/log/nginx/access.log

# ── Security ───────────────────────────────────────────────────
IDS_AES_KEY=<64 hex chars>           # python3 -c "import os; print(os.urandom(32).hex())"

# ── Model ──────────────────────────────────────────────────────
IDS_MODEL_DIR=./model

# ── Geo-location ───────────────────────────────────────────────
IPINFO_TOKEN=                        # optional, increases rate limit to 150k/month

# ── Telegram Notifications ─────────────────────────────────────
TELEGRAM_BOT_TOKEN=                  # from @BotFather
TELEGRAM_CHAT_ID=                    # your numeric chat ID

# ── Debug ──────────────────────────────────────────────────────
DEBUG=false
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | No | — | Enables AI alert enrichment and `/api/analyze`. Without this, static countermeasures are used. |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Which Gemini model to call |
| `CAPTURE_INTERFACE` | **Yes** | `eth0` | NIC to sniff. Use `ip link show` to find yours. |
| `LOG_PATHS` | No | `/var/log/syslog` | Comma-separated log file paths to watch |
| `IDS_AES_KEY` | No | — | 64-char hex string. Without it, alerts stored unencrypted. |
| `IDS_MODEL_DIR` | No | `./model` | Directory containing the 3 `.pkl` files |
| `IPINFO_TOKEN` | No | — | ipinfo.io API token for higher rate limits |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot token for push notifications |
| `TELEGRAM_CHAT_ID` | No | — | Telegram chat/user ID to send notifications to |
| `DEBUG` | No | `false` | Enable verbose debug logging |

---

## 21. Database Schema

SQLite database at `ids_alerts.db`. Single table:

```sql
CREATE TABLE alerts (
    id                TEXT PRIMARY KEY,   -- UUID4
    timestamp         TEXT,               -- ISO 8601 UTC
    attack_type       TEXT,               -- e.g. "Brute Force"
    src_ip            TEXT,               -- attacker IP
    dst_ip            TEXT,               -- target IP
    severity          TEXT,               -- High / Medium / Low
    confidence        REAL,               -- 0.0 – 1.0
    geo_lat           REAL,               -- latitude
    geo_lon           REAL,               -- longitude
    geo_city          TEXT,               -- e.g. "Shanghai"
    geo_country       TEXT,               -- e.g. "CN"
    alert_message     TEXT,               -- one-sentence summary
    countermeasures   TEXT,               -- JSON array of strings
    encrypted_payload TEXT                -- base64(nonce + AES-GCM ciphertext)
);
```

### Useful Queries

```sql
-- Count by attack type
SELECT attack_type, COUNT(*) FROM alerts GROUP BY attack_type;

-- Top attacking IPs
SELECT src_ip, COUNT(*) as cnt FROM alerts
GROUP BY src_ip ORDER BY cnt DESC LIMIT 10;

-- High severity alerts today
SELECT * FROM alerts
WHERE severity = 'High'
  AND timestamp > datetime('now', '-1 day')
ORDER BY timestamp DESC;

-- Hourly activity
SELECT strftime('%Y-%m-%dT%H:00', timestamp) as hour, COUNT(*) as cnt
FROM alerts
WHERE timestamp > datetime('now', '-24 hours')
GROUP BY hour ORDER BY hour;
```

---

## 22. Setup & Installation

### Prerequisites
- Linux (Ubuntu 22.04+ recommended)
- Python 3.11+
- Network interface you want to monitor
- (Optional) sudo or `CAP_NET_RAW` for packet capture
- A free Google AI Studio account for Gemini (optional)

### Step-by-Step

```bash
# 1. Clone the repository
git clone <repo-url>
cd cyber-gym-main

# 2. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Generate AES key
python3 -c "import os; print('IDS_AES_KEY=' + os.urandom(32).hex())"

# 5. Create .env file
cat > .env << EOF
GEMINI_API_KEY=your_key_here
CAPTURE_INTERFACE=wlo1          # change to your interface
IDS_AES_KEY=<paste from step 4>
LOG_PATHS=/var/log/auth.log,/var/log/syslog,/var/log/kern.log
EOF

# 6. Verify your network interface
ip link show

# 7. Start the server (normal mode, no packet capture)
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# 8. Start with packet capture (requires sudo)
sudo ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# 9. Open dashboard
# http://localhost:8000
```

### Using the run.sh Helper
```bash
chmod +x run.sh
./run.sh          # checks deps, kills stale server, starts cleanly
```

### Testing Without Real Traffic
```bash
# Start server in one terminal
./run.sh

# Run a simulated attack in another
curl -s -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "BRUTE_FORCE_SSH", "vm_id": "vm1"}'
```

---

## 23. Security Considerations

### Things That Are Secured
| Area | Mechanism |
|---|---|
| Alert payloads | AES-256-GCM encryption at rest |
| API keys | Stored in `.env`, never in source code |
| IP injection | `escHtml()` prevents XSS in the alert table |
| SQL injection | Parameterized queries throughout `ids/db.py` |
| Gemini quota | Token bucket (10/min) + per-IP caching (60s TTL) |
| Telegram spam | 1-hour dedup per `(src_ip, attack_type)` pair |
| DB size | 7-day auto-rotation on startup |

### Things To Be Aware Of
- The dashboard has **no authentication** — it's designed for a local/trusted network. Add a reverse proxy with authentication (nginx + basic auth, or Cloudflare Access) before exposing publicly.
- Packet capture requires `root` or `CAP_NET_RAW`. Running the full server as root is acceptable in a lab environment but not in production.
- The SQLite database stores IPs and attack metadata in plaintext columns — only the `encrypted_payload` column is encrypted.
- puter.js chatbot sends your alert data (last 20 alerts + 30 log lines) to OpenAI via puter's servers. Don't use on networks where alert data is classified.

---

## 24. Known Limitations

| Limitation | Details |
|---|---|
| No IPv6 support | `ids/capture.py` only processes `IP` layer (IPv4). IPv6 packets are ignored. |
| sklearn version mismatch warning | Model was trained on scikit-learn 1.6.1; current install is 1.8.0. Warnings are cosmetic — inference still works. Retrain the model to eliminate. |
| Flow direction heuristic | "fwd" vs "bwd" is determined by checking if `src_ip` is a local IP. VPN or tunnel traffic may confuse this. |
| 4s flow timeout | Fast port scans complete in <1s; they're still caught within 5s total. Very slow scans (1 probe/5s) appear as separate flows. |
| ML model is a placeholder | The included `.pkl` files are placeholder models. For production use, train on real CIC-IDS2017 data using `create_placeholder_model.py` as a scaffold. |
| Log capture only reads new lines | Lines that existed in the log before the server started are not processed on the first run. |
| No flow reassembly | Each 5-tuple flow is independent. Multi-stage attacks across different connections are not correlated automatically (the AI chatbot can help with this manually). |
| Geo-location accuracy | ipinfo.io provides city-level accuracy (~50km). ASN info is usually accurate. |
| puter.js requires internet | The chatbot requires outbound internet access to puter.com. Air-gapped environments should disable the chatbot. |
