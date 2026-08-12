# Live Packet Capture with Scapy

## How It Works

```
Network Interface
      ↓
Scapy sniff()           ← captures raw packets
      ↓
Flow Buffer             ← groups packets by (src_ip, dst_ip, port)
      ↓
extract_features()      ← computes flow statistics
      ↓
predict_flow()          ← calls the IDS model
      ↓
Alert / Log             ← takes action on result
```

---

## Full Runtime Agent Code

```python
import time
import numpy as np
import joblib
from collections import defaultdict
from scapy.all import sniff, IP, TCP, UDP

# ── Load model once ──────────────────────────────────────────
MODEL_DIR = "./models"
pipeline  = joblib.load(f"{MODEL_DIR}/ids_model.pkl")
le        = joblib.load(f"{MODEL_DIR}/label_encoder.pkl")
features  = joblib.load(f"{MODEL_DIR}/feature_list.pkl")

# ── Flow buffer ───────────────────────────────────────────────
flow_buffer = defaultdict(lambda: {"packets": [], "start": time.time()})

FLOW_PACKET_THRESHOLD = 10      # predict after this many packets
FLOW_TIMEOUT_SECS     = 30      # flush flows older than this


# ── Feature extractor ─────────────────────────────────────────
def extract_features_from_flow(flow: dict) -> dict:
    packets    = flow["packets"]
    start_time = flow["start"]
    duration   = (time.time() - start_time) * 1_000_000
    dur_secs   = max(duration / 1_000_000, 1e-6)

    pkt_sizes  = [len(p) for p in packets]
    fwd_pkts   = packets   # simplified: all treated as forward
    bwd_pkts   = []

    def flag(f, mask): return sum(1 for p in f if p.haslayer(TCP) and p[TCP].flags & mask)

    return {
        "flow_duration":          duration,
        "total_fwd_packets":      len(fwd_pkts),
        "total_backward_packets": len(bwd_pkts),
        "flow_bytes_per_s":       sum(pkt_sizes) / dur_secs,
        "flow_packets_per_s":     len(packets) / dur_secs,
        "packet_length_mean":     float(np.mean(pkt_sizes))   if pkt_sizes else 0.0,
        "packet_length_std":      float(np.std(pkt_sizes))    if pkt_sizes else 0.0,
        "packet_length_variance": float(np.var(pkt_sizes))    if pkt_sizes else 0.0,
        "syn_flag_count":         flag(packets, 0x02),
        "ack_flag_count":         flag(packets, 0x10),
        "rst_flag_count":         flag(packets, 0x04),
        "psh_flag_count":         flag(packets, 0x08),
        "urg_flag_count":         flag(packets, 0x20),
        "average_packet_size":    float(np.mean(pkt_sizes))   if pkt_sizes else 0.0,
        "down_per_up_ratio":      0.0,
        "fwd_packets_per_s":      len(fwd_pkts) / dur_secs,
        "bwd_packets_per_s":      0.0,
        "active_mean":            duration,
        "idle_mean":              0.0,
    }


# ── Predict ───────────────────────────────────────────────────
def predict_flow(flow_stats: dict) -> dict:
    vector = [float(flow_stats.get(f, 0.0)) for f in features]
    X      = np.array(vector, dtype=np.float32).reshape(1, -1)

    pred       = pipeline.predict(X)[0]
    proba      = pipeline.predict_proba(X)[0]
    label      = le.inverse_transform([pred])[0]

    return {
        "label":      label,
        "confidence": float(proba.max()),
        "is_attack":  label != "Benign",
    }


# ── Alert handler ─────────────────────────────────────────────
def handle_result(result: dict, flow_key: tuple):
    src, dst, port = flow_key
    label      = result["label"]
    confidence = result["confidence"]

    if result["is_attack"]:
        if confidence >= 0.90:
            print(f"🚨 ALERT  [{label}] {src} -> {dst}:{port}  confidence={confidence:.2f}")
        elif confidence >= 0.60:
            print(f"⚠️  SUSPICIOUS [{label}] {src} -> {dst}:{port}  confidence={confidence:.2f}")
        else:
            print(f"📋 LOW    [{label}] {src} -> {dst}:{port}  confidence={confidence:.2f}")
    # Benign: no output


# ── Packet handler ────────────────────────────────────────────
def process_packet(pkt):
    if not pkt.haslayer(IP):
        return

    src  = pkt[IP].src
    dst  = pkt[IP].dst
    port = pkt[TCP].dport if pkt.haslayer(TCP) else (pkt[UDP].dport if pkt.haslayer(UDP) else 0)
    key  = (src, dst, port)

    flow_buffer[key]["packets"].append(pkt)

    # Predict after threshold packets
    if len(flow_buffer[key]["packets"]) >= FLOW_PACKET_THRESHOLD:
        flow         = flow_buffer.pop(key)
        flow_stats   = extract_features_from_flow(flow)
        result       = predict_flow(flow_stats)
        handle_result(result, key)


# ── Start capture ─────────────────────────────────────────────
print("IDS Agent started. Listening for packets...")
print(f"Model detects: {list(le.classes_)}")

sniff(
    prn=process_packet,
    store=False,
    filter="ip"       # only capture IP packets
)
```

---

## Running the Agent

```bash
# Must run as root or with sudo for raw packet capture
sudo python ids_agent.py

# Or specify a network interface
sudo python ids_agent.py --iface eth0
```

---

## Flow Key Explained

The flow key `(src_ip, dst_ip, dst_port)` groups packets into flows:

```python
key = (src, dst, port)
# Example: ("192.168.1.5", "10.0.0.1", 22)
#           ↑ attacker       ↑ target    ↑ SSH port
```

Each unique key is one network conversation tracked independently.

---

## Tuning Parameters

| Parameter | Default | Effect |
|---|---|---|
| `FLOW_PACKET_THRESHOLD` | 10 | Lower = faster detection, less accurate |
| `FLOW_TIMEOUT_SECS` | 30 | Flush slow flows (Slowloris detection) |
| Alert threshold | 0.60 | Lower = more alerts, more false positives |
| Alert threshold | 0.90 | Higher = fewer alerts, more false negatives |
