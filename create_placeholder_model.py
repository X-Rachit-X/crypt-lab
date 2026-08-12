"""
create_placeholder_model.py — Generate placeholder .pkl model files for testing.
Run this once to create model/ artifacts before starting Crypt Lab.

Usage: python create_placeholder_model.py
"""

import os
import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier

MODEL_DIR = "./model"
os.makedirs(MODEL_DIR, exist_ok=True)

# Attack classes the model knows
CLASSES = [
    "Benign", "Bot", "Brute Force", "DDoS", "DoS",
    "Heartbleed", "Infiltration", "Port Scan", "Web Attack",
]

# 19 feature names — order is PERMANENT
FEATURE_LIST = [
    "flow_duration",
    "total_fwd_packets",
    "total_backward_packets",
    "flow_bytes_per_s",
    "flow_packets_per_s",
    "packet_length_mean",
    "packet_length_std",
    "packet_length_variance",
    "syn_flag_count",
    "ack_flag_count",
    "rst_flag_count",
    "psh_flag_count",
    "urg_flag_count",
    "average_packet_size",
    "down_per_up_ratio",
    "fwd_packets_per_s",
    "bwd_packets_per_s",
    "active_mean",
    "idle_mean",
]

# ── Build a small synthetic training set ──────────────────────────
np.random.seed(42)
n_per_class = 100
X_all = []
y_all = []

for idx, cls in enumerate(CLASSES):
    # Each class gets a slightly different feature distribution
    center = np.random.rand(19) * 100 + idx * 50
    noise = np.random.randn(n_per_class, 19) * 10
    X_cls = center + noise
    X_cls = np.clip(X_cls, 0, None)  # no negatives
    X_all.append(X_cls)
    y_all.extend([cls] * n_per_class)

X = np.vstack(X_all).astype(np.float32)

# Encode labels
le = LabelEncoder()
y = le.fit_transform(y_all)

# Build pipeline: StandardScaler → RandomForestClassifier
pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)),
])
pipe.fit(X, y)

# ── Save artifacts ────────────────────────────────────────────────
joblib.dump(pipe, os.path.join(MODEL_DIR, "ids_model.pkl"))
joblib.dump(le, os.path.join(MODEL_DIR, "label_encoder.pkl"))
joblib.dump(FEATURE_LIST, os.path.join(MODEL_DIR, "feature_list.pkl"))

print(f"✅ Model files created in '{MODEL_DIR}/':")
for f in ["ids_model.pkl", "label_encoder.pkl", "feature_list.pkl"]:
    size = os.path.getsize(os.path.join(MODEL_DIR, f))
    print(f"   {f} ({size:,} bytes)")
print(f"   Classes: {list(le.classes_)}")
print(f"   Features: {len(FEATURE_LIST)}")
