# 🤝 Contributing to Crypt Lab IDS

Thank you for interest in contributing! This document outlines how to contribute to the project.

---

## 🐛 Reporting Issues

Found a bug? Have a feature request? Open a [GitHub Issue](https://github.com/X-Rachit-X/crypt-lab/issues) with:

1. **Clear title** (e.g., "WebSocket disconnects after 5 minutes")
2. **Reproduction steps**
3. **Expected vs. actual behavior**
4. **Environment**: OS, Python version, branch
5. **Logs**: Include server terminal output or browser console errors

---

## 🚀 Making Changes

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR-USERNAME/crypt-lab.git
cd crypt-lab
```

### 2. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 3. Set Up Development Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your test API keys
```

### 4. Make Your Changes

**Code style:**
- PEP 8 compliant (run `black` for formatting)
- Meaningful commit messages
- Comment complex logic
- Add docstrings to new functions

**Testing:**
- Test changes locally with `./run.sh`
- Use attack simulator to verify detection still works
- Check dashboard loads and WebSocket connects
- Verify no new console errors (F12)

### 5. Commit & Push

```bash
git add .
git commit -m "feat: describe your change"
git push origin feature/your-feature-name
```

### 6. Open a Pull Request

Go to https://github.com/X-Rachit-X/crypt-lab/pulls and create a PR with:

- **Clear title** describing the change
- **Description** of what & why
- **Reference** any related issues (#123)
- **Screenshots** if UI changes

---

## 💡 Areas for Contribution

### High-Priority

- [ ] **Add authentication** (OAuth2/API key) to REST API
- [ ] **Improve ML accuracy** — retrain on real CIC-IDS-2018 dataset
- [ ] **Add unit tests** — pytest framework ready
- [ ] **PostgreSQL support** — replace SQLite for scaling
- [ ] **Telegram notifications** — integrate `ids/notify.py` with dashboard

### Medium-Priority

- [ ] Fix Web Attack class name encoding (UTF-8 mojibake)
- [ ] Add rate limiting to API endpoints
- [ ] Implement data retention policies (auto-delete old alerts)
- [ ] Add export to CSV/JSON
- [ ] Create Docker Compose setup

### Low-Priority

- [ ] UI dark mode themes (currently one theme)
- [ ] Mobile-responsive dashboard
- [ ] Performance benchmarking tools
- [ ] Multi-sensor federation

---

## 📝 Code Architecture Overview

```
main.py (FastAPI)
├─ config.py (load .env)
├─ ids/
│  ├─ engine.py (ML + rules) ← ML features here
│  ├─ aggregator.py (19-feature extraction) ← Feature engineering here
│  ├─ capture.py (Scapy) ← Packet capture here
│  ├─ alerts.py (AES encryption) ← Encryption here
│  ├─ db.py (SQLite) ← Database schema here
│  ├─ llm.py (Gemini) ← AI analysis here
│  ├─ geo.py (ipinfo.io) ← Geo lookups here
│  └─ log_capture.py (watchdog) ← Log parsing here
├─ simulator/ (test attacks)
└─ static/ (frontend dashboard)
```

### Key Editing Locations

| Task | File | Lines |
|------|------|-------|
| Adjust detection thresholds | `ids/engine.py` | ~50–70 |
| Add new attack type | `ids/engine.py` | ~40–65 |
| Modify flow features | `ids/aggregator.py` | ~80–150 |
| Add API endpoint | `main.py` | ~900–1100 |
| Update dashboard | `static/index.html` | ~1–380 |
| Fix chatbot | `static/js/chatbot.js` | ~1–395 |
| Add log parser | `ids/log_capture.py` | ~50–140 |

---

## 🧪 Testing Your Changes

### Run Simulator Locally

```bash
./run.sh
# In another terminal:
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"PORT_SCAN"}'
```

Check dashboard at `http://localhost:8000` — alert should appear in ~10s.

### Check Server Health

```bash
curl http://localhost:8000/api/health
```

### Monitor Server Logs

```bash
# Terminal where you ran ./run.sh
# Watch for [IDS] log lines
```

### Check WebSocket Connection

Open browser console (F12) and check:
```javascript
// Should show successful connection
console.log(app.ws.readyState) // 1 = OPEN
```

---

## 📚 Documentation Standards

When adding features, update:

1. **Code comments** — Explain *why*, not *what*
2. **Docstrings** — Function signature + example
3. **README.md** — If user-visible feature
4. **QUICK_REFERENCE.md** — If new command/endpoint
5. **DOCUMENTATION.md** — Deep technical details

Example docstring:

```python
def classify(feature_vector: List[float]) -> Tuple[str, float]:
    """
    Classify a network flow using hybrid rule+ML approach.
    
    Args:
        feature_vector: 19-element list of flow metrics
        
    Returns:
        (attack_type, confidence): e.g., ("Port Scan", 0.95)
        
    Example:
        >>> classify([1.5, 100, 0.8, ...])
        ("Port Scan", 0.95)
    """
```

---

## 🔒 Security Guidelines

- **Never commit secrets** (.env, API keys, tokens)
- **Validate input** on API endpoints
- **Escape output** in frontend (XSS protection)
- **SQL injection:** Use parameterized queries (already done in `db.py`)
- **Cryptography:** Use proven libraries (cryptography, bcrypt) — don't roll your own
- **Dependencies:** Keep packages updated, review for CVEs

---

## 📋 Pre-Submission Checklist

- [ ] Code follows PEP 8 style
- [ ] All user changes documented
- [ ] No console errors (F12)
- [ ] Server starts without errors (`./run.sh`)
- [ ] Simulator scenarios still work
- [ ] WebSocket connects (indicator green)
- [ ] No secrets committed to git
- [ ] Git history is clean (meaningful commits)
- [ ] Tests pass (if applicable)

---

## 🎯 Review Process

1. **Automated checks**: CI/CD pipeline runs (linting, basic tests)
2. **Code review**: Maintainer reviews for:
   - Code quality & style
   - Security implications
   - Performance impact
   - Backward compatibility
3. **Testing feedback**: If issues found, discuss in PR comments
4. **Merge**: Once approved, changes merged to main

---

## 🕐 Development Tips

### Local Testing Without Root

Use simulator mode (no packet capture needed):

```bash
# Dashboard works fine on simulator
./run.sh
# Don't use --capture flag
```

### Faster Feedback Loop

1. Make code change
2. Save file (auto-reload should trigger)
3. Refresh browser (Ctrl+R)
4. Check browser console (F12)

### Debug ML Model

```python
# In Python REPL
import ids.engine as e
e.load_model('./model')

# Test prediction
flow = [1.5, 100, 0.8, ...]  # 19 features
result = e.classify(flow)
print(result)  # (attack_type, confidence)
```

### Inspect Database

```bash
sqlite3 ids_alerts.db "SELECT src_ip, attack_type, confidence FROM alerts LIMIT 10;"
```

---

## 📞 Getting Help

- **Questions?** Open a GitHub Discussion
- **Chat?** Join our Discord (if available)
- **Docs?** See [README.md](./README.md) & [DOCUMENTATION.md](./DOCUMENTATION.md)
- **Stuck?** Comment on an issue or PR

---

## 🎓 Learning Resources

- **FastAPI:** [Official Tutorial](https://fastapi.tiangolo.com/)
- **scikit-learn:** [User Guide](https://scikit-learn.org/)
- **SQLite:** [Documentation](https://www.sqlite.org/docs.html)
- **Scapy:** [Interactive Tutorial](https://scapy.readthedocs.io/)
- **Security:** [OWASP Top 10](https://owasp.org/www-project-top-ten/)

---

## ✨ Thank You!

Every contribution — code, docs, bug reports, feature ideas — helps make Crypt Lab IDS better. We appreciate you!

---

**License:** Contributions are licensed under the MIT License (see [LICENSE](./LICENSE))

**Code of Conduct:** Be respectful, inclusive, and constructive. We don't tolerate harassment.

---

*Last updated: August 12, 2026*
