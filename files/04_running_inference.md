# Running Inference

## The Predict Function

This is the core function your agent calls for every network flow:

```python
def predict_flow(flow_stats: dict) -> dict:
    """
    flow_stats: dict of {feature_name: numeric_value}

    Returns dict with:
      - label:         string attack class name
      - confidence:    float 0.0 to 1.0
      - is_attack:     bool
      - probabilities: dict of {class_name: probability}
    """
    # Build vector in exact feature order
    vector = [float(flow_stats.get(f, 0.0)) for f in features]
    X      = np.array(vector, dtype=np.float32).reshape(1, -1)

    pred       = pipeline.predict(X)[0]
    proba      = pipeline.predict_proba(X)[0]
    label      = le.inverse_transform([pred])[0]
    confidence = float(proba.max())

    return {
        "label":         label,
        "confidence":    confidence,
        "is_attack":     label != "Benign",
        "probabilities": dict(zip(le.classes_, proba.tolist()))
    }
```

---

## Example Input

```python
flow_stats = {
    "flow_duration":           50000,
    "total_fwd_packets":       500,
    "total_backward_packets":  2,
    "flow_bytes_per_s":        980000.0,
    "flow_packets_per_s":      10000.0,
    "packet_length_mean":      64.0,
    "packet_length_std":       0.5,
    "packet_length_variance":  0.25,
    "syn_flag_count":          498,
    "ack_flag_count":          2,
    "rst_flag_count":          0,
    "psh_flag_count":          0,
    "urg_flag_count":          0,
    "average_packet_size":     64.0,
    "down_per_up_ratio":       0.004,
    "fwd_packets_per_s":       9960.0,
    "bwd_packets_per_s":       40.0,
    "active_mean":             50000,
    "idle_mean":               0.0
}

result = predict_flow(flow_stats)
```

---

## Example Output

```python
{
    "label":      "DDoS",
    "confidence": 0.97,
    "is_attack":  True,
    "probabilities": {
        "Benign":       0.01,
        "Bot":          0.00,
        "Brute Force":  0.00,
        "DDoS":         0.97,
        "DoS":          0.01,
        "Heartbleed":   0.00,
        "Infiltration": 0.00,
        "Port Scan":    0.00,
        "Web Attack":   0.00
    }
}
```

---

## Acting on Results

```python
result = predict_flow(flow_stats)

if result["is_attack"]:

    if result["confidence"] >= 0.90:
        # High confidence — trigger alert immediately
        trigger_alert(
            label      = result["label"],
            confidence = result["confidence"],
            src_ip     = flow_stats.get("src_ip", "unknown")
        )

    elif result["confidence"] >= 0.60:
        # Medium confidence — log and flag for review
        log_suspicious(result)

    else:
        # Low confidence — log only
        log_event(result)

else:
    # Benign traffic — no action needed
    pass
```

---

## Input Rules

| Rule | Detail |
|---|---|
| Feature count | Must match `len(features)` exactly |
| Feature order | Must match `feature_list.pkl` order |
| Data type | All values must be numeric (int or float) |
| Missing values | Use `0.0`, never `None` or `NaN` |
| Pre-scaling | Do NOT scale — pipeline does it automatically |
| Batch size | One flow at a time (reshape to `(1, -1)`) |

---

## Performance

| Metric | Value |
|---|---|
| Prediction time per flow | ~1–5 ms |
| Memory usage | ~500 MB (model loaded in RAM) |
| Throughput | ~200–1000 predictions/sec |

The model is fast enough for real-time packet processing on Kaggle or any server with 2+ GB RAM.
