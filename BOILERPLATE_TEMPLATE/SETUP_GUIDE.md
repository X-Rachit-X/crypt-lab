# Cyber Project Template - Setup & Development Guide

## Quick Start (5 minutes)

### 1. Clone & Enter Template
```bash
cd cyber-project-template
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your Gemini API key (optional)
```

### 4. Run Server
```bash
bash scripts/dev_server.sh
# OR directly:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open Browser
Visit `http://localhost:8000`

Monitor Gemini API calls in real-time: `http://localhost:8000/debug`

---

## File Structure Explained

```
cyber-project-template/
│
├── main.py                          # FastAPI application
│   ├── WebSocket endpoints (/ws/monitor, /ws/stats, /ws/debug)
│   ├── REST APIs (/api/health, /api/analyze, /api/models)
│   └── Debounced analysis_worker()
│
├── config.py                        # Settings from .env
│   └── Settings dataclass with optimization properties
│
├── static/
│   ├── index.html                  # Main UI
│   │   └── Two resource cards with stats + terminal areas
│   │
│   ├── debug.html                  # Debug dashboard
│   │   └── Real-time Gemini API call monitor
│   │
│   ├── js/app.js                   # Frontend module
│   │   └── RealTimeMonitor class
│   │       ├── Visibility-aware stats polling
│   │       └── Auto-reconnect logic
│   │
│   └── css/
│       └── styles.css              # Tailwind + custom themes
│
├── tests/
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_main.py                # Unit tests for endpoints
│   └── test_integration.py         # Integration tests
│
├── scripts/
│   ├── dev_server.sh               # Start dev server
│   └── health_check.sh             # Monitor health via cron
│
├── data/                           # Local data (gitignored)
│   └── config.enc                  # Encrypted credentials
│
├── requirements.txt                 # Python dependencies
├── .env.example                    # Template (safe to commit)
├── .env                            # Local config (gitignored)
├── .gitignore
├── pytest.ini                      # Test configuration
└── README.md
```

---

## Key Components & How They Work

### 1. **RealTimeMonitor Class** (`static/js/app.js`)

Manages WebSocket connections with built-in optimizations:

```javascript
const monitor = new RealTimeMonitor('resource1', {
    onOutput: (msg) => { /* handle terminal output */ },
    onStats: (stats) => { /* update UI metrics */ },
    onAnalysis: (result) => { /* show analysis results */ }
});
```

**Optimization: Page Visibility API**
```javascript
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        monitor.pauseStats();  // Close WebSocket, save bandwidth
    } else {
        monitor.resumeStats(); // Reconnect when tab is visible
    }
});
```

When you switch browser tabs:
- Stats polling **automatically pauses**
- WebSocket connection closes
- Resources are freed
- On return, polling **automatically resumes**

**Result:** ~50% reduction in unnecessary WebSocket traffic

---

### 2. **Analysis Worker** (`main.py`)

Backend debouncing mechanism:

```python
async def analysis_worker(resource_id: str):
    """
    Groups events into time windows before sending to Gemini.
    
    Example:
    - User types command: Event 1 enqueued
    - Event 2 within 2.5s: Added to batch
    - Event 3 within 2.5s: Added to batch
    - Timer expires: Send all 3 events → 1 Gemini API call
    
    Without debounce: 3 API calls
    With debounce: 1 API call (50% reduction)
    """
```

Configuration:
```env
ANALYSIS_DEBOUNCE_MS=2500  # Collect events for 2.5 seconds
ANALYSIS_SAMPLE_SIZE=2000   # Send only last 2000 chars (vs 4000)
```

---

### 3. **WebSocket Endpoints**

| Endpoint | Purpose | Auto-Pause |
|----------|---------|-----------|
| `/ws/monitor/{id}` | Terminal I/O | No (always active) |
| `/ws/stats/{id}` | CPU/memory/disk metrics | **Yes** (pauses when hidden) |
| `/ws/debug` | Gemini API call events | No (debug tool) |

---

## Optimizations at a Glance

### Problem 1: Terminal becomes slow when opening multiple tabs
**Solution:** Page Visibility API pauses stats polling
- **Before:** Stats polled every 2s even if tab is hidden
- **After:** Stats pause automatically on hidden, resume on visible
- **Impact:** ~50% less WebSocket traffic for multi-tab users

### Problem 2: Gemini API quota exhausted quickly
**Solution:** Analysis debouncing + reduced sample size
- **Before:** 1 API call per keystroke/output (~10+ calls per second during active use)
- **After:** 1 API call every 2.5 seconds max + smaller payload
- **Impact:** ~80% fewer API calls

### Problem 3: Network congestion with many resources
**Solution:** Lazy initialization + conditional connecting
- **Before:** All WebSockets open on page load
- **After:** Open only when user interacts with resource
- **Impact:** Faster page load, lower baseline resource usage

---

## Customization Guide

### Add a New Resource Type

**1. In `main.py`, add new WebSocket handler:**
```python
@app.websocket("/ws/custom/{resource_id}")
async def custom_websocket(websocket: WebSocket, resource_id: str):
    await websocket.accept()
    get_or_create_buffers(resource_id)
    # ... custom logic
```

**2. In `static/index.html`, add new card:**
```html
<section id="custom-resource" class="glass-panel rounded-lg p-6">
    <h2>Custom Resource</h2>
    <div id="custom-output"></div>
</section>
```

**3. In `static/js/app.js`, initialize monitor:**
```javascript
const customMonitor = new RealTimeMonitor('custom', {
    onOutput: (msg) => {
        document.getElementById('custom-output').textContent += msg.data;
    }
});
```

### Adjust Debounce Settings

For **faster analysis** (more API calls, lower latency):
```env
ANALYSIS_DEBOUNCE_MS=1000   # Default 2500
ANALYSIS_SAMPLE_SIZE=3000   # Default 2000
```

For **slower analysis** (fewer API calls, higher latency):
```env
ANALYSIS_DEBOUNCE_MS=5000   # Default 2500
ANALYSIS_SAMPLE_SIZE=1000   # Default 2000
```

---

## Testing

### Run Unit Tests
```bash
pytest tests/test_main.py -v
```

### Run All Tests with Coverage
```bash
pytest tests/ --cov=main --cov-report=html
open htmlcov/index.html
```

### Test Specific Function
```bash
pytest tests/test_main.py::TestHealthEndpoint::test_health_returns_ok -v
```

### Add a New Test
```python
# tests/test_main.py

def test_my_feature(self, client):
    response = client.get("/api/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert data["expected_key"] == "expected_value"
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Copy `.env.example` → `.env` and fill real values
- [ ] Verify `GEMINI_API_KEY` is set (if using analysis)
- [ ] Run tests: `pytest tests/ -v`
- [ ] Check `.gitignore` includes `.env` (never commit secrets)
- [ ] Build frontend assets (if using build tools)

### Production Deployment
```bash
# Install production dependencies
pip install -r requirements.txt

# Set production env vars
export GEMINI_API_KEY=your_real_key
export DEBUG=false

# Run with Gunicorn (production ASGI server)
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t cyber-project .
docker run -e GEMINI_API_KEY=your_key -p 8000:8000 cyber-project
```

### Health Monitoring (Cron Job)
```bash
# Every 5 minutes, check service health
*/5 * * * * /bin/bash -lc 'cd /path/to/project && bash scripts/health_check.sh >> health.log 2>&1'
```

---

## Troubleshooting

### **Terminal is slow / lots of errors**

1. **Check stats connection:**
   - Open DevTools (F12)
   - Network tab → Filter by "WS"
   - Look for `/ws/stats` connection
   - Should pause when tab is hidden

2. **Check analysis debounce:**
   - Visit `/debug` dashboard
   - Look for `gemini_call` events
   - Should be ~1 call every 2.5 seconds (not every keystroke)
   - If too frequent, increase `ANALYSIS_DEBOUNCE_MS` in `.env`

3. **Check API quota:**
   - Visit `/debug`
   - Count total `gemini_call` events
   - Check Google Cloud API quota

### **WebSocket connections keep dropping**

- Increase uvicorn timeout: `--timeout-keep-alive 30`
- Check firewall/proxy rules
- Verify browser console for JavaScript errors

### **Analysis never runs**

- Check `ANALYSIS_ENABLED=true` in `.env`
- Verify `GEMINI_API_KEY` is set
- Check `/debug` for `gemini_error` events
- Verify API key has Gemini permissions

---

## Reference Links

- **FastAPI WebSockets:** https://fastapi.tiangolo.com/advanced/websockets/
- **Page Visibility API:** https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
- **Google Gemini API:** https://ai.google.dev/
- **Tailwind CSS:** https://tailwindcss.com/
- **Pytest:** https://docs.pytest.org/

---

## Next Steps

1. **Customize for your use case:**
   - Replace "Resource 1/2" with your resource names
   - Implement actual stats collection (replace mock data)
   - Integrate with your backend systems

2. **Add real data sources:**
   - SSH/Paramiko for remote resources
   - Docker API for containers
   - Kubernetes API for pods
   - Custom APIs/webhooks

3. **Enhance security:**
   - Implement authentication/authorization
   - Use HTTPS/WSS in production
   - Encrypt sensitive data
   - Validate all inputs

4. **Monitor and scale:**
   - Set up logging (Sentry, ELK, CloudWatch)
   - Monitor API quota usage
   - Auto-scale backend resources
   - Cache analysis results

---

## Support & Issues

- **For bugs:** Create an issue with reproduction steps
- **For features:** Open a discussion or PR
- **For security:** Report privately to maintainers

---

**Built with ❤️ based on CyberGym (X-Rachit-X/CyberGym)**
