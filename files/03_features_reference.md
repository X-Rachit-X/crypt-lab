# Features Reference

## Critical Rule

The model expects features in **exactly the order stored in `feature_list.pkl`**.
Always build your input vector by iterating over the loaded `features` list — never hardcode positions.

---

## Standard Feature List (19 features)

| Index | Feature Name | Unit | Description |
|---|---|---|---|
| 00 | `flow_duration` | microseconds | Total duration of the flow |
| 01 | `total_fwd_packets` | count | Packets sent from source to destination |
| 02 | `total_backward_packets` | count | Packets sent from destination to source |
| 03 | `flow_bytes_per_s` | bytes/sec | Total bytes transferred per second |
| 04 | `flow_packets_per_s` | packets/sec | Total packets per second |
| 05 | `packet_length_mean` | bytes | Average packet size in the flow |
| 06 | `packet_length_std` | bytes | Standard deviation of packet sizes |
| 07 | `packet_length_variance` | bytes² | Variance of packet sizes |
| 08 | `syn_flag_count` | count | Number of SYN TCP flags |
| 09 | `ack_flag_count` | count | Number of ACK TCP flags |
| 10 | `rst_flag_count` | count | Number of RST TCP flags |
| 11 | `psh_flag_count` | count | Number of PSH TCP flags |
| 12 | `urg_flag_count` | count | Number of URG TCP flags |
| 13 | `average_packet_size` | bytes | Mean size of all packets |
| 14 | `down_per_up_ratio` | ratio | Download-to-upload packet ratio |
| 15 | `fwd_packets_per_s` | packets/sec | Forward direction packet rate |
| 16 | `bwd_packets_per_s` | packets/sec | Backward direction packet rate |
| 17 | `active_mean` | microseconds | Mean active flow time |
| 18 | `idle_mean` | microseconds | Mean idle time between bursts |

---

## How to Build the Feature Vector

```python
def build_feature_vector(flow_stats: dict, features: list) -> np.ndarray:
    """
    flow_stats: dict of {feature_name: value} from your flow extractor
    features:   list loaded from feature_list.pkl

    Returns: np.ndarray of shape (1, n_features) dtype float32
    """
    vector = [float(flow_stats.get(f, 0.0)) for f in features]
    return np.array(vector, dtype=np.float32).reshape(1, -1)
```

---

## Missing Feature Rule

If a feature cannot be computed from a packet (e.g. no backward packets exist yet):
- Use `0.0` as the default value
- Do NOT use `None`, `NaN`, or skip the feature
- Do NOT pass fewer features than expected

---

## Feature Attack Signals (what to watch)

| Feature | High Value Indicates | Low Value Indicates |
|---|---|---|
| `syn_flag_count` | SYN flood / Port Scan | Normal |
| `rst_flag_count` | Port Scan / connection resets | Normal |
| `flow_bytes_per_s` | DDoS / data exfiltration | Normal |
| `flow_packets_per_s` | DDoS flood | Normal |
| `packet_length_variance` | Mixed attack traffic | Uniform (bot or scan) |
| `idle_mean` | Slow DoS (Slowloris) | Normal |
| `down_per_up_ratio` | Data exfiltration (high download) | Normal |
| `urg_flag_count` | Heartbleed / exploit attempts | Normal |

---

## Feature Extraction from Scapy Packets

```python
import time
import numpy as np
from scapy.all import IP, TCP, UDP

def extract_features_from_flow(packets: list, start_time: float) -> dict:
    """
    packets:    list of Scapy packets in this flow
    start_time: Unix timestamp when flow started
    """
    now = time.time()
    flow_duration = (now - start_time) * 1_000_000   # convert to microseconds

    fwd_pkts = [p for p in packets if p.haslayer(IP)]
    bwd_pkts = []   # requires directional tracking

    pkt_sizes = [len(p) for p in packets]
    fwd_sizes = [len(p) for p in fwd_pkts]

    syn_count = sum(1 for p in packets if p.haslayer(TCP) and p[TCP].flags & 0x02)
    ack_count = sum(1 for p in packets if p.haslayer(TCP) and p[TCP].flags & 0x10)
    rst_count = sum(1 for p in packets if p.haslayer(TCP) and p[TCP].flags & 0x04)
    psh_count = sum(1 for p in packets if p.haslayer(TCP) and p[TCP].flags & 0x08)
    urg_count = sum(1 for p in packets if p.haslayer(TCP) and p[TCP].flags & 0x20)

    total_bytes   = sum(pkt_sizes)
    duration_secs = max(flow_duration / 1_000_000, 1e-6)

    return {
        "flow_duration":            flow_duration,
        "total_fwd_packets":        len(fwd_pkts),
        "total_backward_packets":   len(bwd_pkts),
        "flow_bytes_per_s":         total_bytes / duration_secs,
        "flow_packets_per_s":       len(packets) / duration_secs,
        "packet_length_mean":       float(np.mean(pkt_sizes)) if pkt_sizes else 0.0,
        "packet_length_std":        float(np.std(pkt_sizes))  if pkt_sizes else 0.0,
        "packet_length_variance":   float(np.var(pkt_sizes))  if pkt_sizes else 0.0,
        "syn_flag_count":           syn_count,
        "ack_flag_count":           ack_count,
        "rst_flag_count":           rst_count,
        "psh_flag_count":           psh_count,
        "urg_flag_count":           urg_count,
        "average_packet_size":      float(np.mean(pkt_sizes)) if pkt_sizes else 0.0,
        "down_per_up_ratio":        len(bwd_pkts) / max(len(fwd_pkts), 1),
        "fwd_packets_per_s":        len(fwd_pkts) / duration_secs,
        "bwd_packets_per_s":        len(bwd_pkts) / duration_secs,
        "active_mean":              flow_duration,
        "idle_mean":                0.0,
    }
```
