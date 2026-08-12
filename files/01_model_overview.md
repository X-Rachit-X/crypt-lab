# IDS Model Overview

## What This Model Is

A **Behavior-Based Intrusion Detection System (IDS)** trained on the CIC-IDS2017 dataset.
It classifies network flows as either **Benign** or one of **8 attack types**.

---

## Architecture

```
Raw Network Flow
      ↓
StandardScaler      ← normalizes all feature values
      ↓
RandomForestClassifier (100 trees, depth 20)
      ↓
Attack Label + Confidence Score
```

The scaler and classifier are bundled together inside `ids_model.pkl` as a single sklearn Pipeline.
You never need to scale input manually — just pass raw feature values.

---

## Files the Agent Must Have

| File | Purpose |
|---|---|
| `ids_model.pkl` | Full pipeline: scaler + trained Random Forest |
| `label_encoder.pkl` | Converts numeric prediction → attack name string |
| `feature_list.pkl` | Ordered list of features the model expects |

All 3 files are required. The model will crash if any are missing.

---

## What the Model Detects

| Label | Attack Type | Example |
|---|---|---|
| `Benign` | Normal traffic | Regular HTTP, DNS |
| `DDoS` | Distributed flood | UDP flood, ICMP flood |
| `DoS` | Single-source flood | Hulk, GoldenEye, Slowloris |
| `Brute Force` | Password guessing | SSH-Patator, FTP-Patator |
| `Bot` | Botnet C2 traffic | Automated bot behavior |
| `Port Scan` | Network reconnaissance | PortScan |
| `Web Attack` | Application layer attacks | SQLi, XSS, Web Brute Force |
| `Heartbleed` | Memory leak exploit | CVE-2014-0160 |
| `Infiltration` | Internal network infiltration | Internal pivot |

---

## How Confident Should You Trust It

| Confidence | Meaning | Action |
|---|---|---|
| > 0.90 | Very high | Trigger alert immediately |
| 0.60 – 0.90 | Medium | Log and flag for review |
| < 0.60 | Low | Log only, do not alert |

Recommended alert threshold: **confidence > 0.60**

---

## What the Model Does NOT Do

- Does NOT inspect packet payloads (it uses flow statistics only)
- Does NOT work on raw `.pcap` files directly
- Does NOT maintain state between calls — each flow is independent
- Does NOT detect zero-day attacks (only trained attack types above)
