# Quick Reference Card

## Startup Checklist

```
[ ] ids_model.pkl present in model directory
[ ] label_encoder.pkl present in model directory
[ ] feature_list.pkl present in model directory
[ ] joblib, numpy, scapy, sklearn installed
[ ] Agent running as root (for packet capture)
```

---

## Minimal Working Agent (20 lines)

```python
import joblib, numpy as np
from scapy.all import sniff, IP, TCP

pipeline = joblib.load("ids_model.pkl")
le       = joblib.load("label_encoder.pkl")
features = joblib.load("feature_list.pkl")
flows    = {}

def process(pkt):
    if not pkt.haslayer(IP): return
    key = (pkt[IP].src, pkt[IP].dst)
    flows.setdefault(key, []).append(pkt)
    if len(flows[key]) >= 10:
        pkts   = flows.pop(key)
        sizes  = [len(p) for p in pkts]
        stats  = {"flow_duration": 1e5, "total_fwd_packets": len(pkts),
                  "packet_length_mean": float(np.mean(sizes)),
                  "flow_packets_per_s": len(pkts) / 0.1}
        vec    = np.array([float(stats.get(f, 0.0)) for f in features], dtype=np.float32).reshape(1,-1)
        label  = le.inverse_transform(pipeline.predict(vec))[0]
        if label != "Benign":
            print(f"ATTACK: {label} from {key[0]}")

sniff(prn=process, store=False)
```

---

## Predict Output Fields

| Field | Type | Example |
|---|---|---|
| `label` | string | `"DDoS"` |
| `confidence` | float 0–1 | `0.97` |
| `is_attack` | bool | `True` |
| `probabilities` | dict | `{"Benign": 0.01, "DDoS": 0.97, ...}` |

---

## Attack Classes

| Label | Typical Confidence |
|---|---|
| `Benign` | > 0.95 (very clean) |
| `DDoS` | > 0.90 |
| `DoS` | > 0.85 |
| `Port Scan` | > 0.90 |
| `Brute Force` | > 0.80 |
| `Bot` | > 0.75 |
| `Web Attack` | > 0.70 |
| `Heartbleed` | > 0.85 |
| `Infiltration` | > 0.60 (hardest to detect) |

---

## Key Rules — Never Forget

```
1. Load 3 pkl files once at startup
2. Feature order must match feature_list.pkl exactly
3. Missing features → use 0.0
4. Input dtype → float32
5. Do NOT pre-scale input (pipeline does it)
6. Alert threshold → confidence > 0.60
7. flow_duration must be in MICROSECONDS
8. flow_bytes_per_s = total_bytes / duration_in_SECONDS
```

---

## File Summary

| File | What it contains |
|---|---|
| `01_model_overview.md` | What the model does, attack classes, confidence guide |
| `02_loading_the_model.md` | How to load the 3 pkl files at startup |
| `03_features_reference.md` | All features, units, extraction from Scapy |
| `04_running_inference.md` | predict_flow() function, input/output examples |
| `05_live_packet_capture.md` | Full Scapy runtime agent code |
| `06_error_handling.md` | Common errors, fixes, safe predict wrapper |
| `07_quick_reference.md` | This file — minimal code + rules summary |
