# Cyber Project Template

A FastAPI + WebSocket cybersecurity monitoring platform with optimized real-time analysis and minimal API overhead.

**Based on:** CyberGym (X-Rachit-X/CyberGym)

---

## Features

- **Real-time WebSocket communication** for terminal I/O and system metrics
- **Debounced AI analysis** (Gemini) to reduce API call spam
- **Page Visibility API** to pause non-critical polling when tab is hidden
- **Encrypted credential storage** for secure VM configuration
- **Async workers** for background processing without blocking the main event loop
- **Debug monitoring** WebSocket for observability and troubleshooting

---

## Prerequisites

- Python 3.10+
- Google Gemini API key (optional, for analysis features)

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -U fastapi uvicorn[standard] python-dotenv google-generativeai
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Gemini API key and settings
```

### 3. Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open in browser

Visit `http://localhost:8000`

---

## Project Structure

```
cyber-project-template/
├── main.py                          # FastAPI app + WebSocket handlers
├── config.py                        # Settings loader
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template (safe, no secrets)
├── .env                             # Local config (gitignored)
├── .gitignore
├── README.md
├── pytest.ini
│
├── static/
│   ├── index.html                  # Main UI
│   ├── js/
│   │   └── app.js                  # Frontend class-based modules
│   │       └── RealTimeMonitor     # Visibility-aware polling
│   └── css/
│       └── styles.css              # Tailwind + custom styling
│
├── scripts/
│   ├── dev_server.sh               # Development server launcher
│   ├── health_check.sh             # Monitoring health check
│   └── e2e_test.py                 # End-to-end integration tests
│
├── tests/
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_main.py                # Unit tests
│   └── test_integration.py         # Integration tests
│
└── data/
    └── config.enc                  # Encrypted credentials (gitignored)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (empty) | Google Gemini API key for AI analysis |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `ANALYSIS_ENABLED` | `true` | Enable real-time analysis |
| `ANALYSIS_SAMPLE_SIZE` | `2000` | Max chars to send to Gemini per analysis |
| `ANALYSIS_DEBOUNCE_MS` | `2500` | Min milliseconds between analysis calls |
| `DEBUG` | `false` | Enable verbose logging |

---

## API Overview

### WebSocket Endpoints

- **`/ws/monitor/{resource_id}`** – Real-time resource monitoring (terminal I/O, logs, etc.)
  - **Message format (server → client):**
    ```json
    {
      "type": "output",
      "data": "terminal output or resource data"
    }
    ```
  - **Message format (client → server):**
    ```json
    {
      "type": "input",
      "data": "user input or command"
    }
    ```

- **`/ws/stats/{resource_id}`** – System metrics (CPU, memory, disk, load)
  - Sends updates every 2 seconds
  - **Optimized:** Pauses automatically when page is hidden (Page Visibility API)
  - **Message format:**
    ```json
    {
      "type": "stats",
      "data": {
        "cpu": 45.2,
        "memory": 62.5,
        "disk": 38.1,
        "load": 1.23
      }
    }
    ```

- **`/ws/analysis/{resource_id}`** – Real-time AI analysis results
  - **Message format:**
    ```json
    {
      "type": "analysis",
      "data": {
        "status": "ok",
        "security_analysis": "Summary of findings",
        "detections": ["anomaly1", "anomaly2"],
        "recommendations": ["action1", "action2"]
      }
    }
    ```

- **`/ws/debug`** – Debug event stream (Gemini call monitoring, errors)

### REST Endpoints

- **`GET /api/health`** – Service status and connection counts
- **`POST /api/analyze`** – Manual analysis request
  ```json
  {
    "logs": "terminal output to analyze",
    "resource_id": "optional_id"
  }
  ```
- **`GET /api/models`** – List available Gemini models
- **`GET /debug`** – Debug dashboard HTML

---

## Optimization Strategy: Reducing API Calls

### **1. Frontend: Page Visibility API**
Automatically pauses stats polling when the user switches tabs. Resumes on return.

```javascript
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        monitor.pauseStats();  // Closes WebSocket, saves bandwidth
    } else {
        monitor.resumeStats(); // Reconnects when tab is visible
    }
});
```

### **2. Backend: Analysis Debouncing**
Groups terminal events into windows (default 2.5 seconds) before sending to Gemini. Reduces API calls by ~50% vs. per-keystroke analysis.

```python
async def analysis_worker(resource_id: str):
    debounce_sec = settings.ANALYSIS_DEBOUNCE_MS / 1000
    while True:
        evt = await analysis_queue.get()
        last_ts = time.time()
        # Drain additional events during debounce window
        while (time.time() - last_ts) < debounce_sec:
            try:
                await asyncio.wait_for(analysis_queue.get(), timeout=...)
            except asyncio.TimeoutError:
                break
        # Now send aggregated analysis to Gemini (single API call per window)
        result = await send_to_gemini(logs)
```

### **3. Reduced Sample Size**
Send only the last 2000 characters to Gemini instead of 4000. Fewer tokens = faster, cheaper API calls.

```env
ANALYSIS_SAMPLE_SIZE=2000
```

### **4. Conditional Stats Updates**
Only send stats when page is active. Reduces unnecessary WebSocket connections and server load.

---

## Testing

### Unit Tests
```bash
pytest tests/test_main.py -v
```

### Integration Tests (mocking Gemini)
```bash
pytest tests/test_integration.py -v
```

### End-to-End Tests (real resources, if available)
```bash
export GEMINI_API_KEY=<your_key>
python scripts/e2e_test.py
```

### Coverage Report
```bash
pytest tests/ --cov=main --cov-report=html
open htmlcov/index.html
```

---

## Troubleshooting

### **Symptom: Slow terminal, lots of API errors**
**Solution:**
1. Check `.env` settings:
   - Increase `ANALYSIS_DEBOUNCE_MS` to 3000–5000
   - Reduce `ANALYSIS_SAMPLE_SIZE` to 1000
2. Ensure browser tab visibility controls are working (open DevTools → Application → Manifest)
3. Monitor Gemini quota: Check `/debug` dashboard

### **Symptom: Stats not updating**
**Solution:**
1. Check browser console for WebSocket errors
2. Verify `/ws/stats/{resource_id}` endpoint is available
3. Try manual tab reload: `Ctrl+F5` (hard refresh)
4. Check if page was hidden (see Page Visibility API behavior)

### **Symptom: Analysis never runs**
**Solution:**
1. Verify `ANALYSIS_ENABLED=true` in `.env`
2. Check `GEMINI_API_KEY` is set and valid
3. Monitor `/ws/debug` WebSocket for error events
4. Run `python scripts/verify_gemini.py` to test API key

---

## Reference & Further Reading

- **FastAPI WebSocket docs:** https://fastapi.tiangolo.com/advanced/websockets/
- **Page Visibility API:** https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
- **Google Gemini API:** https://ai.google.dev/
- **xterm.js (terminal UI):** https://xtermjs.org/

---

## License

Based on CyberGym by X-Rachit-X. Modify and distribute freely for educational purposes.

