"""
ids/engine.py — Load trained ML model and classify flow feature vectors.
"""

import os
import sys
import logging
import numpy as np

logger = logging.getLogger("ids.engine")

# Module-level model artifacts (loaded once at startup)
pipeline = None
le = None
features = None


def load_model(model_dir: str):
    """
    Load the three .pkl files from *model_dir*.
    Exits the process if any file is missing.
    """
    global pipeline, le, features
    import joblib

    required = ["ids_model.pkl", "label_encoder.pkl", "feature_list.pkl"]
    for fname in required:
        path = os.path.join(model_dir, fname)
        if not os.path.isfile(path):
            logger.error(
                f"FATAL: Model file missing: {path}  "
                f"Place all 3 .pkl files in '{model_dir}/' before starting."
            )
            sys.exit(1)

    pipeline = joblib.load(os.path.join(model_dir, "ids_model.pkl"))
    le = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))
    features = joblib.load(os.path.join(model_dir, "feature_list.pkl"))

    logger.info(
        f"Model loaded from '{model_dir}' — "
        f"{len(features)} features, "
        f"{len(le.classes_)} classes: {list(le.classes_)}"
    )


def classify(feature_vec: np.ndarray) -> dict:
    """
    Classify a 19-element feature vector.

    Returns dict with keys:
        label, confidence, is_attack, source, all_probs
    """
    # ── Feature index constants (never hardcode these elsewhere) ──
    # 0  flow_duration        4  flow_packets_per_s   8  syn_flag_count
    # 1  total_fwd_packets    5  packet_length_mean   9  ack_flag_count
    # 2  total_bwd_packets    6  packet_length_std   10  rst_flag_count
    # 3  flow_bytes_per_s     7  packet_length_var   11  psh_flag_count
    #                                                12  urg_flag_count
    # 13 average_packet_size 14 down_per_up_ratio
    # 15 fwd_packets_per_s   16 bwd_packets_per_s
    # 17 active_mean         18 idle_mean

    fwd_pps   = float(feature_vec[4])
    fwd_pkts  = float(feature_vec[1])
    pkt_mean  = float(feature_vec[5])
    syn_cnt   = float(feature_vec[8])
    ack_cnt   = float(feature_vec[9])
    rst_cnt   = float(feature_vec[10])
    urg_cnt   = float(feature_vec[12])
    bytes_ps  = float(feature_vec[3])

    # ── Rule-based fast path ──────────────────────────────────────
    # These cover simulator scenarios and obvious real-traffic patterns.

    # DoS / DDoS flood: extreme packet rate.
    # Threshold is 50k pps — real floods sustain this; normal bursty traffic
    # (video calls, large downloads) peaks at ~5–15k pps at most.
    if fwd_pps > 50_000:
        label = "DDoS" if float(feature_vec[2]) > 10 else "DoS"
        return _result(label, 0.99, source="rule")

    # Brute Force: RST-heavy with high packet rate (credential stuffing,
    # each attempt = SYN → RST/ACK reject cycle, fast rate)
    if rst_cnt > 50 and fwd_pps > 500 and fwd_pkts > 100:
        return _result("Brute Force", 0.93, source="rule")

    # Port scan: RST-heavy but SLOWER rate (systematic port enumeration)
    if rst_cnt > 30 and fwd_pkts > 100 and pkt_mean < 120:
        return _result("Port Scan", 0.95, source="rule")

    # SYN flood: many SYNs, almost no ACKs, minimal RST
    if syn_cnt > 100 and ack_cnt < 20 and rst_cnt < 30:
        return _result("DoS", 0.97, source="rule")

    # Port scan fallback: many small-packet fwd flows, minimal backward response
    if fwd_pkts > 200 and pkt_mean < 80 and float(feature_vec[2]) < 10:
        return _result("Port Scan", 0.95, source="rule")

    # Heartbleed indicator: very large average packet size + URG flags
    if pkt_mean > 1500 and urg_cnt > 1:
        return _result("Heartbleed", 0.90, source="rule")

    # High-bandwidth flood
    if bytes_ps > 5_000_000:
        return _result("DDoS", 0.96, source="rule")

    # ── ML path ───────────────────────────────────────────────────
    if pipeline is None or le is None:
        return _result("Unknown", 0.5, source="rule")

    X = feature_vec.reshape(1, -1).astype(np.float32)
    pred = pipeline.predict(X)[0]
    proba = pipeline.predict_proba(X)[0]
    label = le.inverse_transform([pred])[0]
    conf = float(proba.max())

    all_probs = {}
    for cls_idx, cls_name in enumerate(le.classes_):
        all_probs[cls_name] = float(proba[cls_idx])

    # ── Second-opinion: class-imbalance correction ────────────────
    # CIC-IDS2017 is ~80% Benign, so the model is biased toward Benign.
    # When ML votes Benign but with < 0.80 confidence, check whether any
    # attack class has ≥ 0.20 probability — if so, use it as the label.
    if label == "Benign" and conf < 0.80:
        attack_probs = {k: v for k, v in all_probs.items() if k != "Benign"}
        if attack_probs:
            best_attack = max(attack_probs, key=attack_probs.get)
            best_attack_conf = attack_probs[best_attack]
            if best_attack_conf >= 0.20:
                logger.debug(
                    f"Second-opinion override: Benign({conf:.0%}) → "
                    f"{best_attack}({best_attack_conf:.0%})"
                )
                return {
                    "label": best_attack,
                    "confidence": best_attack_conf,
                    "is_attack": True,
                    "source": "ml_second_opinion",
                    "all_probs": all_probs,
                }

    return {
        "label": label,
        "confidence": conf,
        "is_attack": label != "Benign",
        "source": "ml",
        "all_probs": all_probs,
    }


def _result(label: str, confidence: float, source: str = "rule") -> dict:
    return {
        "label": label,
        "confidence": confidence,
        "is_attack": label != "Benign",
        "source": source,
        "all_probs": {label: confidence},
    }
