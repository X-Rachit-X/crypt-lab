# CRYPT LAB — AGENT BRIEF v3
# Behavior-Based IDS with AI-Powered Alert Intelligence
# Feed this entire file to your agent before starting any work.

---

## WHO YOU ARE & WHAT YOU ARE BUILDING

You are building **Crypt Lab** — a fully operational, AI-powered Network Intrusion
Detection System. This is not a toy demo. Every module must work end-to-end in a
real network environment.

You are extending an existing FastAPI project called the CyberGym template.
That project already has: FastAPI server, WebSocket infrastructure, Tailwind
dashboard, debounced analysis worker, and a RealTimeMonitor JS class.
**Extend it. Do not rewrite it.**

---

## PROJECT REQUIREMENTS (what the finished system must do)

### REQ-1: Capture
The system must continuously capture live network packets from the machine's
network interface AND watch system log files for suspicious entries.
Both data sources feed into the same detection pipeline.

### REQ-2: Analyze
Every captured network flow must be converted into a 19-feature behavioral
vector and classified by a trained Random Forest model. The model output is
a traffic label (e.g. "Port Scan", "DoS") and a confidence score.
The system must also apply fast rule-based checks before hitting the ML model.

### REQ-3: Enrich with AI
Every detected attack must be sent to Gemini (LLM). Gemini must return:
- A plain-English alert message (one sentence, readable by non-experts)
- A technical summary (2-3 sentences for a security analyst)
- 4 specific countermeasures the admin should take right now
- An explanation of why the severity level was assigned

### REQ-4: Geolocate
Every attacking IP must be resolved to a latitude/longitude coordinate.
The result must include city, country, and ISP/org information.

### REQ-5: Store Securely
Every alert must be encrypted with AES-256-GCM before being written to the
database. The encryption key lives only in the environment — never in code.

### REQ-6: Display on Dashboard
The dashboard must show all of the following in real time:
- A live alert feed table with LLM-generated messages
- A world map with animated markers at each attacking IP's location
- A chart showing the distribution of attack types
- A countermeasures panel showing what to do about the latest threat
- A live log viewer showing raw captured log lines
- An attack simulator panel for controlled demonstrations

### REQ-7: Simulate
The system must include a built-in attack simulator that triggers realistic
detection events without needing external tools like nmap or hping3.
Simulation must work with a single button click on the dashboard.

---

## PROJECT OBJECTIVES

### OBJ-1: Detect encrypted traffic attacks
Most modern traffic is HTTPS/TLS. The system must detect attacks by analyzing
behavioral patterns (packet rates, timing, flag counts) — not packet contents.
This is why behavioral features are used instead of deep packet inspection.

### OBJ-2: Provide actionable intelligence, not just alerts
Raw "Port Scan detected" alerts are not useful. The LLM layer transforms every
detection into a human-readable explanation with specific remediation steps.
A non-expert reading the dashboard must understand what happened and what to do.

### OBJ-3: Operate in real time
From packet capture to dashboard display, the full pipeline latency must be
under 10 seconds for network flows (30-second flow timeout + processing).
Log-based detections must appear on the dashboard within 3 seconds.

### OBJ-4: Cover multiple attack surfaces
The system must detect attacks coming through two channels:
- Network layer: packet-based flows analyzed by the ML model
- System layer: log file entries indicating auth failures, scans, exploits

### OBJ-5: Be secure by design
Alert data is sensitive. The system must encrypt every alert before storage.
The encryption key must never appear in source code or be committed to git.

### OBJ-6: Be demonstrable without a real attacker
The simulation module exists so the system can be demonstrated in any
environment. Every attack type must be triggerable with one click.

---

## THE MODEL ARTIFACTS

The ML model has already been trained separately. Three files will be placed
in the `model/` folder before the system is started. Do not train, retrain,
or modify these files. Just load and use them.

```
model/
├── ids_model.pkl        ← sklearn Pipeline(StandardScaler → RandomForestClassifier)
├── label_encoder.pkl    ← sklearn LabelEncoder
└── feature_list.pkl     ← Python list of 19 feature name strings
```

### How to load them (copy this exactly into ids/engine.py):
```python
import joblib, numpy as np

pipeline = joblib.load("model/ids_model.pkl")
le       = joblib.load("model/label_encoder.pkl")
features = joblib.load("model/feature_list.pkl")

# Inference — always reshape to (1, 19)
X     = np.array(feature_vector, dtype=np.float32).reshape(1, -1)
pred  = pipeline.predict(X)[0]
proba = pipeline.predict_proba(X)[0]
label = le.inverse_transform([pred])[0]
conf  = float(proba.max())
```

### Attack classes the model knows:
```
Benign, Bot, Brute Force, DDoS, DoS, Heartbleed, Infiltration, Port Scan, Web Attack
```

---

## FILE STRUCTURE

```
crypt-lab/
│
├── main.py                     MODIFY — add new endpoints + start IDS threads
├── config.py                   MODIFY — add new env vars
├── requirements.txt            MODIFY — add new packages
├── .env                        MODIFY — add new keys
│
├── ids/                        NEW PACKAGE
│   ├── __init__.py
│   ├── capture.py              NEW — Scapy live packet capture thread
│   ├── log_capture.py          NEW — System log file watcher
│   ├── aggregator.py           NEW — Flow grouping + 19-feature extraction
│   ├── engine.py               NEW — Load model + classify flows
│   ├── llm.py                  NEW — Gemini: alert message + countermeasures
│   ├── alerts.py               NEW — Build alert dict + AES-256-GCM encrypt
│   ├── geo.py                  NEW — IP geolocation with cache
│   └── db.py                   NEW — SQLite store + query functions
│
├── simulator/
│   ├── __init__.py
│   ├── simulator.py            NEW — Inject fake attack events into pipeline
│   └── templates.py            NEW — Pre-built attack scenario definitions
│
├── model/                      PRE-POPULATED — do not touch
│   ├── ids_model.pkl
│   ├── label_encoder.pkl
│   └── feature_list.pkl
│
├── static/
│   ├── index.html              MODIFY — add all new dashboard panels
│   └── js/
│       ├── app.js              MODIFY — extend RealTimeMonitor
│       ├── map.js              NEW — Leaflet map controller
│       └── simulator.js        NEW — Simulator control panel UI
│
└── ids_alerts.db               AUTO-CREATED at first run
```

---

## FULL PIPELINE — HOW DATA FLOWS

```
INGESTION
─────────────────────────────────────────────────────────────
[ids/capture.py]                    [ids/log_capture.py]
Scapy sniff() — daemon thread       watchdog FileWatcher — daemon thread
Extracts per-packet dicts           Tails log files for new lines
         │                                      │
         └──────────────┬─────────────────────── ┘
                        │
                        ▼
AGGREGATION
─────────────────────────────────────────────────────────────
[ids/aggregator.py]
Packets → grouped by 5-tuple flow key
Flow complete after 30s inactivity
→ compute 19-feature vector (see FEATURES section)

Log lines → parsed into structured log event dicts
→ put directly into detection queue
                        │
                        ▼
DETECTION
─────────────────────────────────────────────────────────────
[ids/engine.py]
Rule check first (fast path):
  pkt_rate > 10,000/s          → "DoS"
  many small fwd pkts          → "Port Scan"
  high SYN, near-zero ACK      → "DoS"

If no rule fires → ML model:
  pipeline.predict_proba(feature_vec)
  → label + confidence

If label == "Benign" → discard, loop back
If label != "Benign" → continue to enrichment
                        │
                        ▼
ENRICHMENT  (run geo + LLM in parallel with asyncio.gather)
─────────────────────────────────────────────────────────────
[ids/geo.py]                        [ids/llm.py]
ipinfo.io lookup                    Gemini API call
→ lat, lon, city, country, org      → alert_message
                                    → technical_summary
                                    → countermeasures [list of 4]
                                    → threat_level_explanation
         │                                      │
         └──────────────┬─────────────────────── ┘
                        │
                        ▼
STORAGE
─────────────────────────────────────────────────────────────
[ids/alerts.py]
Build complete alert dict (see ALERT STRUCTURE section)
AES-256-GCM encrypt → base64 token

[ids/db.py]
Store to SQLite:
  - Decrypted fields for fast dashboard reads
  - encrypted_payload as audit record
                        │
                        ▼
PRESENTATION
─────────────────────────────────────────────────────────────
[main.py]
Broadcast to /ws/ids-feed → all connected dashboard clients

[static/index.html + js/]
Alert table, map marker, chart update, countermeasures panel
— all update in real time from the WebSocket push
```

---

## MODULE SPECS

### ids/capture.py

Purpose: Capture live packets from the network interface.
Runs as: daemon thread, started in main.py on startup.
Requires: root or CAP_NET_RAW privilege.

Per-packet dict output format:
```python
{
    "source":    "packet",
    "timestamp": float,       # time.time()
    "src_ip":    str,
    "dst_ip":    str,
    "src_port":  int,
    "dst_port":  int,
    "proto":     int,         # 6=TCP, 17=UDP, 1=ICMP
    "size":      int,         # total packet length in bytes
    "hdr_len":   int,         # IP header length in bytes
    "direction": str,         # "fwd" if src is local machine, else "bwd"
    "syn":       int,         # 1 if TCP SYN flag set, else 0
    "fin":       int,
    "rst":       int,
    "psh":       int,
    "ack":       int,
    "urg":       int,
    "win":       int,         # TCP window size, 0 for non-TCP
}
```

Key rules:
- Use scapy sniff(iface=INTERFACE, prn=callback, store=False)
- store=False is mandatory — prevents memory leak on long captures
- Only process packets with an IP layer
- Call aggregator.add_packet(pkt_info) for every packet

---

### ids/log_capture.py

Purpose: Watch system log files for new lines indicating attacks.
Runs as: daemon thread using watchdog library.
Log files: read from LOG_PATHS env var (comma-separated paths).

Per-log-event dict output format:
```python
{
    "source":    "log",
    "timestamp": float,
    "log_file":  str,         # which file this came from
    "raw_line":  str,         # original log line text
    "log_type":  str,         # see detection patterns below
    "src_ip":    str | None,  # extracted IP address if found in line
    "severity":  str,         # "High" | "Medium" | "Low"
}
```

Detection patterns (regex match on each new line):
```
"Failed password"           → log_type="auth_failure",         severity=High
"Invalid user"              → log_type="auth_failure",         severity=High
"POSSIBLE BREAK-IN ATTEMPT" → log_type="auth_failure",         severity=High
"Accepted password"         → log_type="ssh_success",          severity=Low
"sudo:"                     → log_type="privilege_escalation", severity=High
HTTP 404 burst >20 in 10s   → log_type="http_scan",            severity=Medium
HTTP 500 burst              → log_type="http_error",           severity=Medium
```

IP extraction regex: r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'

Implementation: Use watchdog Observer + FileSystemEventHandler.
On file modification, seek to last-read byte position and read only new lines.
Put each parsed event into a shared asyncio.Queue.

---

### ids/aggregator.py

Purpose: Group packets into flows. Compute 19 features per flow.
Flow key: tuple(src_ip, dst_ip, src_port, dst_port, proto)
Flow timeout: 30 seconds of inactivity.

THE 19 FEATURES — THIS ORDER IS PERMANENT. NEVER CHANGE IT.

```
Index | Name                    | Computation
------+-------------------------+-----------------------------------------------
  0   | flow_duration           | max(timestamps) - min(timestamps), floor 1e-6
  1   | total_fwd_packets       | count where direction == "fwd"
  2   | total_backward_packets  | count where direction == "bwd"
  3   | flow_bytes_per_s        | sum(all sizes) / flow_duration
  4   | flow_packets_per_s      | total packet count / flow_duration
  5   | packet_length_mean      | mean of all packet sizes
  6   | packet_length_std       | std of all packet sizes
  7   | packet_length_variance  | std^2 of all packet sizes
  8   | syn_flag_count          | sum of pkt["syn"] for all packets
  9   | ack_flag_count          | sum of pkt["ack"]
 10   | rst_flag_count          | sum of pkt["rst"]
 11   | psh_flag_count          | sum of pkt["psh"]
 12   | urg_flag_count          | sum of pkt["urg"]
 13   | average_packet_size     | same value as packet_length_mean
 14   | down_per_up_ratio       | sum(bwd sizes) / sum(fwd sizes), 0.0 if fwd empty
 15   | fwd_packets_per_s       | fwd count / flow_duration
 16   | bwd_packets_per_s       | bwd count / flow_duration
 17   | active_mean             | 0.0 (not computable in real-time, placeholder)
 18   | idle_mean               | 0.0 (not computable in real-time, placeholder)
```

Output: np.array of shape (19,), dtype=float32
Safety rule: any division by zero or empty list → use 0.0, never NaN or None.

---

### ids/engine.py

Purpose: Classify a flow feature vector as an attack type or Benign.

Rule-based fast path (check these BEFORE calling the ML model):
```
feature[4] > 10000                              → label="DoS",       source="rule"
feature[1] > 500 AND feature[5] < 100          → label="Port Scan", source="rule"
feature[8] > 200 AND feature[9] < 10           → label="DoS",       source="rule"
```

ML path (when no rule fires):
```python
X     = feature_vec.reshape(1, -1).astype(np.float32)
pred  = pipeline.predict(X)[0]
proba = pipeline.predict_proba(X)[0]
label = le.inverse_transform([pred])[0]
conf  = float(proba.max())
```

Return format:
```python
{
    "label":      str,    # class name
    "confidence": float,  # 0.0 to 1.0
    "is_attack":  bool,   # True if label != "Benign"
    "source":     str,    # "rule" or "ml"
    "all_probs":  dict,   # { class_name: probability, ... }
}
```

---

### ids/llm.py

Purpose: Generate human-readable alert intelligence using Gemini.
Call only when is_attack == True.
Model: gemini-1.5-flash (fast, cheap, good at structured output).

Context dict passed to Gemini:
```python
{
    "attack_type":        str,
    "src_ip":             str,
    "dst_ip":             str,
    "dst_port":           int,
    "protocol":           int,
    "confidence":         float,
    "severity":           str,
    "geo_city":           str,
    "geo_country":        str,
    "flow_packets_per_s": float,
    "flow_bytes_per_s":   float,
    "syn_flag_count":     int,
    "packet_length_mean": float,
    "log_events":         list,   # recent log lines from same src_ip, max 5
}
```

Gemini prompt template:
```
You are a cybersecurity expert analyzing a live network intrusion.

Attack Context:
- Type: {attack_type}
- Source: {src_ip} ({geo_city}, {geo_country})
- Target: {dst_ip}:{dst_port}
- Confidence: {confidence:.0%}  |  Severity: {severity}
- Traffic: {flow_packets_per_s:.0f} packets/s, {flow_bytes_per_s:.0f} bytes/s
- SYN flags: {syn_flag_count}  |  Mean packet size: {packet_length_mean:.0f} bytes
- Related log events: {log_events}

Respond ONLY with this JSON structure. No markdown. No extra text.
{
  "alert_message": "One sentence describing the attack and its risk for a general audience.",
  "technical_summary": "2-3 sentences with technical detail for a security analyst.",
  "countermeasures": [
    "Immediate action 1",
    "Immediate action 2",
    "Preventive action 3",
    "Monitoring action 4"
  ],
  "threat_level_explanation": "One sentence explaining the severity assignment."
}
```

Caching: cache responses keyed on (attack_type, src_ip) for 60 seconds.
Rate limit: max 10 calls per minute using a token bucket.
Timeout: 3 seconds. If exceeded, return the fallback response below.

Fallback (when Gemini fails or times out):
```python
{
    "alert_message": f"{attack_type} detected from {src_ip} ({geo_city}, {geo_country}) with {confidence:.0%} confidence.",
    "technical_summary": f"Automated ML detection flagged suspicious {attack_type} traffic pattern from {src_ip}.",
    "countermeasures": [
        f"Block {src_ip} at the perimeter firewall immediately.",
        "Review all traffic from this IP in the past 30 minutes.",
        "Check for lateral movement from this source to other hosts.",
        "Escalate to the security team if the pattern continues."
    ],
    "threat_level_explanation": f"Classified as {severity} based on attack type and observed traffic volume."
}
```

---

### ids/geo.py

Purpose: Resolve IP addresses to geographic coordinates for the map.
API: ipinfo.io — GET https://ipinfo.io/{ip}?token={IPINFO_TOKEN}
The "loc" field returns "lat,lon" as a string. Parse it.

Output format:
```python
{
    "ip":      str,
    "lat":     float,
    "lon":     float,
    "city":    str,
    "region":  str,
    "country": str,
    "org":     str,    # ISP / ASN
}
```

Cache: dict of { ip: (result, expiry_timestamp) }, TTL = 3600 seconds.
Timeout: 2 seconds on the ipinfo.io request.

Private IP ranges — return this placeholder, do NOT call ipinfo.io:
```
10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8
→ { "ip": ip, "lat": 0.0, "lon": 0.0, "city": "Local Network",
    "country": "Internal", "region": "", "org": "Private" }
```
Private IPs must NOT be shown as markers on the map.

---

### ids/alerts.py

Purpose: Assemble the complete alert dict. Encrypt it.

Complete alert dict structure:
```python
{
    # Identity
    "id":                       str,    # uuid4()
    "timestamp":                str,    # datetime.utcnow().isoformat()

    # Detection
    "attack_type":              str,
    "confidence":               float,
    "severity":                 str,    # see severity rules below
    "source":                   str,    # "rule" or "ml"

    # Network
    "src_ip":                   str,
    "dst_ip":                   str,
    "src_port":                 int,
    "dst_port":                 int,
    "protocol":                 int,

    # Geo
    "geo_lat":                  float,
    "geo_lon":                  float,
    "geo_city":                 str,
    "geo_country":              str,
    "geo_org":                  str,

    # LLM
    "alert_message":            str,
    "technical_summary":        str,
    "countermeasures":          list,   # list of 4 strings
    "threat_level_explanation": str,

    # Logs
    "related_logs":             list,   # log lines from same src_ip, max 5
}
```

Severity rules:
```
High:   DoS, DDoS, Bot, Heartbleed, Infiltration
Medium: Port Scan, Brute Force, Web Attack
Low:    anything else
```

Encryption:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64, os, json

key   = bytes.fromhex(os.environ["IDS_AES_KEY"])   # 32 bytes
nonce = os.urandom(12)
ct    = AESGCM(key).encrypt(nonce, json.dumps(alert).encode(), None)
token = base64.b64encode(nonce + ct).decode()
```

---

### ids/db.py

SQLite table schema:
```sql
CREATE TABLE IF NOT EXISTS alerts (
    id                    TEXT PRIMARY KEY,
    timestamp             TEXT,
    attack_type           TEXT,
    src_ip                TEXT,
    dst_ip                TEXT,
    severity              TEXT,
    confidence            REAL,
    geo_lat               REAL,
    geo_lon               REAL,
    geo_city              TEXT,
    geo_country           TEXT,
    alert_message         TEXT,
    countermeasures       TEXT,    -- JSON array as string
    encrypted_payload     TEXT     -- full encrypted alert blob
);
```

Functions to implement:
```
init_db()                     → create table if not exists
store_alert(alert, encrypted) → INSERT OR IGNORE
fetch_alerts(limit=50)        → list of dicts, newest first
fetch_stats()                 → { attack_type: count }
fetch_map_data()              → [{ src_ip, lat, lon, city, country, attack_type, severity }]
fetch_countermeasures()       → countermeasures list from most recent High/Medium alert
```

---

### simulator/

Purpose: Inject realistic attack events directly into the detection pipeline.
No external tools required. Works with zero network access.

How it works: Creates fake flow feature vectors and fake log entries that match
the statistical patterns the ML model was trained on. These are injected
directly into the aggregator queue, bypassing Scapy entirely.

The 5 scenarios (defined in templates.py):

```
PORT_SCAN
  src_ip: "185.220.101.45"  (Tor exit node — will geolocate to Germany)
  total_fwd_packets: 600, packet_length_mean: 44, syn_flag_count: 580
  flow_packets_per_s: 120
  Expected: "Port Scan", confidence >0.90

DOS_FLOOD
  src_ip: "91.108.4.1"  (will geolocate to Russia)
  flow_packets_per_s: 15000, syn_flag_count: 350, ack_flag_count: 2
  Expected: "DoS" via rule engine (fast path)

BRUTE_FORCE_SSH
  src_ip: "218.92.0.1"  (will geolocate to China)
  Injects 50 log lines: "Failed password for root from 218.92.0.1"
  into auth.log watcher queue
  Expected: "Brute Force" from log_capture module

WEB_SCAN
  src_ip: "104.21.0.1"  (will geolocate to United States)
  Injects 50 nginx access log lines with 404 responses
  Expected: "Web Attack" from log_capture module

DDOS
  5 simultaneous flows from: 185.220.101.45, 91.108.4.1, 218.92.0.1,
                              104.21.0.1, 45.33.32.156
  Each with flow_packets_per_s: 12000
  Expected: Multiple "DDoS" alerts, multiple map markers
```

API endpoint: POST /api/simulate
Body: { "scenario": "PORT_SCAN" }
Response: { "status": "started", "scenario": str, "expected_seconds": int }

---

## API ENDPOINTS (add to main.py)

```
GET  /api/alerts
     → last 50 alerts, all fields, newest first
     → used by alert table

GET  /api/stats
     → { "Port Scan": 12, "DoS": 8, ... }
     → used by doughnut chart

GET  /api/map
     → [{ src_ip, lat, lon, city, country, attack_type, severity, timestamp }]
     → used by Leaflet map on page load

GET  /api/logs
     → last 100 raw log events
     → used by log viewer on page load

POST /api/simulate
     → triggers a simulation scenario
     → used by simulator panel buttons

WS   /ws/ids-feed
     → pushes full alert JSON to all connected clients on every new alert
     → drives real-time updates of table, map, chart, countermeasures

WS   /ws/log-feed
     → pushes each new log event as it is captured
     → drives live log viewer
```

---

## DASHBOARD PANELS (static/index.html)

Six panels. All update in real time without page refresh.

### Panel 1 — Live Alert Feed
Columns: Time | Attack Type | Source IP | Location | Severity | Confidence | Message
Severity badges: High=red bg, Medium=amber bg, Low=green bg
Clicking a row expands it to show technical_summary and the 4 countermeasures
as a numbered list. Collapse on second click.
New alerts animate in at the top. Table max 50 rows — oldest drops off.

### Panel 2 — Attack Map
Leaflet.js world map. Centered [20, 0], zoom 2.
Each alert = a circle marker at the attacker's lat/lon.
  - High = red pulsing marker
  - Medium = orange marker
  - Low = green marker
Marker radius scales with confidence (0.9 → large, 0.5 → small).
Click marker → popup: IP, city, country, attack type, alert_message.
New markers are added live via /ws/ids-feed — do not reload the full map.
Private IPs (Local Network) are hidden — do not show a marker at 0,0.

### Panel 3 — Attack Distribution Chart
Chart.js doughnut. Attack type → count.
Total count shown in the center of the doughnut.
Updates every time a new alert arrives on the WebSocket.

### Panel 4 — Countermeasures Panel
Title: "⚠ Recommended Actions"
Shows the 4 countermeasures from the most recent High severity alert.
If no High alert yet, shows most recent Medium.
Each countermeasure = numbered step with an icon.
Flashes briefly (border pulse) when updated with a new alert.

### Panel 5 — Live Log Viewer
Terminal-style scrolling display. Monospace font, dark background.
Color coding:
  auth_failure         → red text
  privilege_escalation → red text
  http_scan            → orange text
  ssh_success          → green text
  generic              → white text
Pause button freezes the scroll. Resume resumes.
Data from /ws/log-feed.

### Panel 6 — Attack Simulator
Title: "Attack Simulator"
5 buttons: [Port Scan] [DoS Flood] [Brute Force SSH] [Web Scan] [DDoS]
On click:
  1. POST /api/simulate with scenario name
  2. Show status bar: "Running: PORT_SCAN — detection expected in ~5s"
  3. Progress bar animates over the expected detection window
  4. When a matching alert arrives on /ws/ids-feed: flash "✅ Detected by IDS"
  5. Reset after 3 seconds
Only one simulation can run at a time. Disable buttons during active simulation.

---

## ENVIRONMENT VARIABLES

Add to .env:
```env
# Keep existing vars unchanged
GEMINI_API_KEY=your_gemini_key_here
ANALYSIS_DEBOUNCE_MS=2500

# New IDS vars
IDS_MODEL_DIR=./model
IDS_AES_KEY=<generate: python -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())">
CAPTURE_INTERFACE=eth0
LOG_PATHS=/var/log/syslog,/var/log/auth.log,/var/log/nginx/access.log
IPINFO_TOKEN=<free token from ipinfo.io — register at ipinfo.io/signup>
```

Add to config.py:
```python
IDS_MODEL_DIR:     str = "./model"
IDS_AES_KEY:       str = ""
CAPTURE_INTERFACE: str = "eth0"
LOG_PATHS:         str = "/var/log/syslog"
IPINFO_TOKEN:      str = ""
```

Add to requirements.txt:
```
scapy>=2.5.0
cryptography>=42.0.0
scikit-learn>=1.4.0
joblib>=1.3.0
watchdog>=4.0.0
requests>=2.31.0
google-generativeai>=0.5.0
```

---

## STARTUP SEQUENCE (main.py)

When the FastAPI app starts, it must launch these threads/tasks in order:

```python
@app.on_event("startup")
async def startup():
    db.init_db()                           # create SQLite table if not exists
    engine.load_model(config.IDS_MODEL_DIR) # load all 3 pkl files

    # Start background threads (all daemon=True)
    threading.Thread(target=capture.start,
                     args=(config.CAPTURE_INTERFACE, aggregator),
                     daemon=True).start()

    threading.Thread(target=log_capture.start,
                     args=(config.LOG_PATHS.split(","), detection_queue),
                     daemon=True).start()

    # Start async detection loop
    asyncio.create_task(detection_loop())
```

The detection loop pulls from the shared queue, runs the full pipeline
(engine → geo + llm in parallel → build alert → encrypt → store → broadcast).

---

## AGENT HARD RULES

1. Feature vector must be exactly 19 values in the order specified. Never change the order.
2. Always use 0.0 for any uncomputable feature value. Never use NaN or None.
3. Call Gemini ONLY for is_attack == True flows. Never waste an API call on Benign.
4. IDS_AES_KEY comes from os.environ only. It must never appear in source code.
5. All background threads must be daemon=True so the app shuts down cleanly.
6. Scapy requires root. Add a startup check and print a clear error if not running as root.
7. Cache geo lookups for 1 hour. Cache Gemini responses for 60 seconds per (attack_type, src_ip).
8. Store alert_message and countermeasures as plain text in SQLite for fast reads.
   Store encrypted_payload as the tamper-evident audit record.
9. Simulator bypasses Scapy entirely — it injects feature vectors and log events
   directly into the internal queues. It must work without network access.
10. Private IPs (10.x, 192.168.x, 172.16-31.x, 127.x) must never appear as
    map markers. Skip geo lookup entirely for private IPs.
11. If the model/ folder is missing or any .pkl file is absent, print a clear
    error message and exit — do not start the app with a broken model state.
12. The existing template's WebSocket endpoints, debounce logic, and RealTimeMonitor
    class must remain untouched and fully functional after your changes.
