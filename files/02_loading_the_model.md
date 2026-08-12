# Loading the Model

## When to Load

Load all 3 model files **once at agent startup**.
Do NOT reload them on every prediction — it wastes time and memory.

---

## Load Code

```python
import joblib
import numpy as np
import os

MODEL_DIR = "./models"   # folder where your .pkl files are stored

# Load once at startup
pipeline = joblib.load(os.path.join(MODEL_DIR, "ids_model.pkl"))
le       = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))
features = joblib.load(os.path.join(MODEL_DIR, "feature_list.pkl"))

print(f"Model loaded successfully")
print(f"Expects {len(features)} features")
print(f"Can detect classes: {list(le.classes_)}")
```

---

## Verify Features After Loading

Always print and verify the feature list after loading:

```python
print("Features the model expects (in this exact order):")
for i, f in enumerate(features):
    print(f"  {i:02d}. {f}")
```

This is critical — if your feature order does not match, predictions will be wrong.

---

## Expected Output After Loading

```
Model loaded successfully
Expects 19 features
Can detect classes: ['Benign', 'Bot', 'Brute Force', 'DDoS', 'DoS',
                     'Heartbleed', 'Infiltration', 'Port Scan', 'Web Attack']

Features the model expects (in this exact order):
  00. flow_duration
  01. total_fwd_packets
  02. total_backward_packets
  03. flow_bytes_per_s
  04. flow_packets_per_s
  05. packet_length_mean
  06. packet_length_std
  07. packet_length_variance
  08. syn_flag_count
  09. ack_flag_count
  10. rst_flag_count
  11. psh_flag_count
  12. urg_flag_count
  13. average_packet_size
  14. down_per_up_ratio
  15. fwd_packets_per_s
  16. bwd_packets_per_s
  17. active_mean
  18. idle_mean
```

> **Note:** Your actual feature list may differ if you used the expanded 70+ feature version.
> Always trust `feature_list.pkl` over this document.

---

## Error Handling at Load Time

```python
def load_ids_model(model_dir):
    required_files = ["ids_model.pkl", "label_encoder.pkl", "feature_list.pkl"]

    for f in required_files:
        path = os.path.join(model_dir, f)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required model file missing: {path}")

    pipeline = joblib.load(os.path.join(model_dir, "ids_model.pkl"))
    le       = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))
    features = joblib.load(os.path.join(model_dir, "feature_list.pkl"))

    return pipeline, le, features
```
