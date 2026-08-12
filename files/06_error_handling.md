# Error Handling and Edge Cases

## Common Errors and Fixes

---

### 1. Missing Model Files

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'ids_model.pkl'
```

**Fix:**
```python
import os

MODEL_DIR = "./models"

for fname in ["ids_model.pkl", "label_encoder.pkl", "feature_list.pkl"]:
    path = os.path.join(MODEL_DIR, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing: {path}. Download from Kaggle /kaggle/working/")
```

---

### 2. Wrong Number of Features

**Error:**
```
ValueError: X has 15 features, but RandomForestClassifier is expecting 19 features
```

**Fix:**
```python
# Always build vector from feature_list.pkl — never hardcode length
vector = [float(flow_stats.get(f, 0.0)) for f in features]

# Verify before predicting
assert len(vector) == len(features), f"Feature count mismatch: {len(vector)} vs {len(features)}"
```

---

### 3. NaN or Infinity in Input

**Error:**
```
ValueError: Input X contains NaN or infinity
```

**Fix:**
```python
import numpy as np

def sanitize_vector(vector: list) -> np.ndarray:
    arr = np.array(vector, dtype=np.float32)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr.reshape(1, -1)
```

Common causes: division by zero in `flow_bytes_per_s` when `duration = 0`.
Always use `max(duration, 1e-6)` as the denominator.

---

### 4. Flow Duration Zero

**Cause:** Two packets arrive at the exact same timestamp.

**Fix:**
```python
duration_secs = max((time.time() - flow["start"]), 1e-6)
```

---

### 5. No TCP Layer (UDP/ICMP Flows)

**Cause:** Accessing `pkt[TCP].flags` on a UDP packet crashes.

**Fix:**
```python
def flag_count(packets, mask):
    return sum(
        1 for p in packets
        if p.haslayer(TCP) and (p[TCP].flags & mask)
    )
```

---

### 6. TerminatedWorkerError (Out of Memory)

**Error:**
```
TerminatedWorkerError: SIGKILL(-9)
```

**Cause:** Cross-validation using `n_jobs=-1` runs 5 full model copies in parallel.

**Fix:** Skip cross-validation entirely for Kaggle. Use test set evaluation instead.

---

### 7. Model Predicts Everything as Benign

**Cause:** Feature values are all zeros or in wrong scale.

**Debug:**
```python
# Check what your vector looks like
print("Feature vector:", list(zip(features, vector)))

# Check what the model sees internally
X = np.array(vector, dtype=np.float32).reshape(1, -1)
print("Probabilities:", dict(zip(le.classes_, pipeline.predict_proba(X)[0])))
```

**Fix:** Verify units. `flow_duration` must be in **microseconds**, not seconds.
`flow_bytes_per_s` must be total bytes / duration in seconds.

---

## Safe Predict Wrapper

Use this in production to catch all errors gracefully:

```python
def safe_predict(flow_stats: dict) -> dict:
    try:
        vector = [float(flow_stats.get(f, 0.0)) for f in features]
        arr    = np.nan_to_num(
                     np.array(vector, dtype=np.float32),
                     nan=0.0, posinf=0.0, neginf=0.0
                 ).reshape(1, -1)

        pred       = pipeline.predict(arr)[0]
        proba      = pipeline.predict_proba(arr)[0]
        label      = le.inverse_transform([pred])[0]

        return {
            "label":      label,
            "confidence": float(proba.max()),
            "is_attack":  label != "Benign",
            "error":      None
        }

    except Exception as e:
        return {
            "label":      "Unknown",
            "confidence": 0.0,
            "is_attack":  False,
            "error":      str(e)
        }
```

---

## Edge Cases Summary

| Situation | Behavior | Action |
|---|---|---|
| Only 1 packet in flow | Predict anyway with partial features | Use `0.0` for missing stats |
| UDP flow (no TCP flags) | All flag counts = 0 | Normal, model handles it |
| ICMP ping flood | Detected as DDoS or DoS | Expected behavior |
| Encrypted HTTPS | Limited feature signal | May classify as Benign |
| IPv6 packets | Not supported | Skip if no IPv4 layer |
| Loopback (127.0.0.1) | Not real traffic | Filter out in agent |
