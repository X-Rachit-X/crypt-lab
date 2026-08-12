# 📑 Crypt Lab IDS — Complete File Index & Navigation

## 📚 Documentation

| File | Purpose | Read When |
|------|---------|-----------|
| [README.md](./README.md) | **START HERE** — Full overview, setup, features, API, dashboard guide | First thing, always |
| [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) | Command cheat sheet, essential endpoints, quick troubleshooting | You need to look something up fast |
| [DOCUMENTATION.md](./DOCUMENTATION.md) | Deep technical details — architecture, every module, data flow | Understanding how things work |
| [INDEX.md](./INDEX.md) | This file — file organization and navigation | Finding specific files |

---

## 🔧 Core Backend (`ids/`)

### Detection Engine

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---|
| **engine.py** | 98 | ML classification + rule engine | `classify()`, `load_model()`, `predict_with_confidence()` |
| **aggregator.py** | 191 | Flow extraction (19 features, 5s windows) | `add_packet()`, `finalize_flows()`, `_compute_features()` |
| **capture.py** | 117 | Scapy packet sniffer | `start()`, `stop()`, raw socket capture |

### Alert Processing

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---|
| **alerts.py** | 96 | Alert builder + AES-256-GCM encryption | `build_alert()`, `encrypt_payload()`, field assembly |
| **db.py** | 132 | SQLite persistence | `init_db()`, `save_alert()`, `get_alerts()`, `get_stats()` |

### External Enrichment

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---|
| **geo.py** | 90 | IP geo-location via ipinfo.io | `lookup()`, async requests, fallback handling |
| **llm.py** | 185 | Gemini API calls for countermeasures | `generate_countermeasures()`, rate limit cache, fallback text |

### Log Monitoring

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---|
| **log_capture.py** | 148 | Watchdog file monitoring | `start()`, `parse_auth_log()`, `parse_nginx_log()`, pattern matching |

---

## 🎮 Attack Simulator (`simulator/`)

| File | Lines | Purpose | Key Classes/Functions |
|------|-------|---------|---|
| **simulator.py** | 75 | Scenario runner | `run_scenario()`, async flow injection, progress broadcast |
| **templates.py** | 164 | 6 attack scenario templates | `PORT_SCAN`, `DOS_FLOOD`, `BRUTE_FORCE_SSH`, `WEB_SCAN`, `DDOS`, `HEARTBLEED` |

---

## 🚀 Main Application

| File | Lines | Purpose | Key Modules |
|------|-------|---------|---|
| **main.py** | 1341 | FastAPI app — core server | `app`, `startup()`, `detection_loop()`, all REST endpoints, WebSocket handlers |
| **config.py** | 26 | Settings loader | `load_config()`, environment variables |

---

## 🖥️ Frontend (`static/`)

### HTML & CSS

| File | Lines | Purpose |
|------|-------|---------|
| **index.html** | 380 | Main dashboard (CSS Grid, 8 panels, dark theme) |
| **css/styles.css** | | Custom Tailwind overrides (if any) |

### JavaScript Modules

| File | Lines | Purpose | Key Classes/Functions |
|------|-------|---------|---|
| **js/app.js** | 465 | Dashboard controller | `DashboardApp`, `connectWebSocket()`, `updateAlerts()`, timer logic |
| **js/chatbot.js** | 395 | AI chatbot module | `ChatBot`, `sendMessage()`, puter.js integration, streaming |
| **js/map.js** | 94 | Leaflet map manager | `MapManager`, `addMarker()`, CartoDB integration |
| **js/simulator.js** | 125 | Simulator UI panel | `SimulatorUI`, button wiring, progress bar |

---

## 🤖 ML Model (`model/`)

| File | Size | Purpose |
|------|------|---------|
| **ids_model.pkl** | 2.1 GB | scikit-learn Pipeline: StandardScaler + RandomForest (300 trees) |
| **label_encoder.pkl** | 636 bytes | Class label encoder (11 attack types) |
| **feature_list.pkl** | 376 bytes | Ordered list of 19 feature names |

**Note:** Pre-trained model. To retrain, see [DOCUMENTATION.md](./DOCUMENTATION.md#ml-model-details).

---

## 🛠️ Utilities & Scripts

| File | Purpose |
|------|---------|
| **create_placeholder_model.py** | Regenerate .pkl files if model/ is missing (for testing) |
| **run.sh** | Server startup/shutdown with options (recommended entry point) |
| **requirements.txt** | Python dependencies (pip install -r requirements.txt) |
| **pytest.ini** | pytest configuration (if tests are added) |
| **.env** | Configuration secrets (NEVER commit) |
| **.env.example** | Template for .env (commit this, not .env) |

---

## 🎯 Where to Edit for Common Tasks

| Task | File(s) | Approx. Location |
|------|---------|------------------|
| Add new attack type | `ids/engine.py` | Rule engine (classify method) |
| Modify ML features | `ids/aggregator.py` | Compute features method |
| Change detection threshold | `ids/engine.py` | Rule conditions (~line 50) |
| Add log parser | `ids/log_capture.py` | Parse methods |
| Customize alert fields | `ids/alerts.py` | build_alert() |
| New API endpoint | `main.py` | Around line 500+ (@app.get/@app.post) |
| Dashboard layout | `static/index.html` | CSS Grid section |
| Chatbot behavior | `static/js/chatbot.js` | System prompt |
| Simulator scenario | `simulator/templates.py` | Template functions |

---

## 📖 Reading Order

**For newcomers:**
1. README.md → Get overview
2. QUICK_REFERENCE.md → See essential commands
3. static/index.html → Understand dashboard layout
4. main.py → Follow startup() logic
5. ids/engine.py → See classification pipeline
6. ids/aggregator.py → Understand feature extraction

**For operators:**
1. README.md → Setup & configuration
2. QUICK_REFERENCE.md → Commands & endpoints
3. Troubleshooting section in README.md
4. `/api/health` endpoint status
5. Dashboard log viewer

**For developers:**
1. DOCUMENTATION.md → Full architecture
2. main.py → Entry point
3. ids/engine.py + ids/aggregator.py → Core logic
4. ids/db.py → Data persistence
5. static/js/app.js → Frontend state

---

## 🔒 Security-Related Files

| File | Concern | Action |
|------|---------|--------|
| `.env` | **Contains secrets** | Add to `.gitignore` (never commit) |
| `ids/alerts.py` | AES-256-GCM key | Use strong random key in `.env` |
| `ids/llm.py` | Gemini API key | Use restricted key with quota limits |
| `main.py` | API endpoints | Add OAuth2/API key auth in production |
| `model/ids_model.pkl` | Model extraction | Large file (2.1 GB); consider separate storage |

---

## 📦 Key Dependencies

| Package | Used In | Version |
|---------|---------|---------|
| fastapi | main.py | 0.109.0 |
| scikit-learn | ids/engine.py | 1.8.0 |
| scapy | ids/capture.py | 2.5.0 |
| watchdog | ids/log_capture.py | 4.0 |
| google-genai | ids/llm.py | latest |
| cryptography | ids/alerts.py | 42.0.0 |
| requests | ids/geo.py | latest |
| python-dotenv | config.py | latest |
| aiofiles | main.py | latest |

---

## 🚀 Deployment Checklist

- [ ] `.env` configured with valid API keys
- [ ] `.gitignore` includes `.env`, `__pycache__/`, `.ids_server.pid`
- [ ] `ids_alerts.db` permissions set: `chmod 600`
- [ ] Firewall allows port 8000 (or configured port)
- [ ] Network interface in `.env` matches actual machine
- [ ] Database WAL mode enabled (`ids/db.py` line ~30)
- [ ] Logs readable (or run with elevated privileges)
- [ ] Model pickle files present and readable (`ls -lh model/`)
- [ ] Test with simulator: `curl -X POST http://localhost:8000/api/simulate`
- [ ] Check dashboard: `http://localhost:8000`

---

**Last updated:** August 12, 2026  
**Total project size:** ~2.2 GB (mostly ML model)  
**Total Python LOC:** ~2500 lines  
**Total frontend LOC:** ~1000 lines
