"""
ids/aggregator.py — Group packets into flows and compute 19-feature vectors.
"""

import time
import asyncio
import logging
import threading
import numpy as np
from typing import Dict, List, Tuple

logger = logging.getLogger("ids.aggregator")

# Flow timeout in seconds — 4s catches fast attacks (port scans, DoS bursts) very quickly
FLOW_TIMEOUT = 4.0

# Minimum packets required before a flow is sent for classification.
# Flows with fewer packets almost always produce wildly inaccurate pps values
# (division by near-zero duration) which trigger false DoS/DDoS rules.
MIN_FLOW_PACKETS = 5

# Minimum effective flow duration used when computing per-second rates.
# Prevents 1–2 packet flows from producing millions of pps (e.g. 2 pkts / 1µs).
MIN_FLOW_DURATION = 0.1  # seconds


class FlowAggregator:
    """
    Collects packets, groups by 5-tuple flow key, and when a flow
    expires (30s inactivity) computes the 19-feature vector and
    pushes it into the detection queue.
    """

    def __init__(self, detection_queue: asyncio.Queue, loop=None):
        self._flows: Dict[Tuple, List[dict]] = {}
        self._last_seen: Dict[Tuple, float] = {}
        self._lock = threading.Lock()
        self._detection_queue = detection_queue
        self._loop = loop
        # Start reaper thread
        t = threading.Thread(target=self._reaper, daemon=True)
        t.start()

    def set_loop(self, loop):
        self._loop = loop

    def add_packet(self, pkt: dict):
        """Add a parsed packet dict (from capture.py) to the appropriate flow."""
        key = (
            pkt["src_ip"],
            pkt["dst_ip"],
            pkt["src_port"],
            pkt["dst_port"],
            pkt["proto"],
        )
        with self._lock:
            self._flows.setdefault(key, []).append(pkt)
            self._last_seen[key] = time.time()

    def inject_flow(self, feature_vector: np.ndarray, meta: dict):
        """
        Directly inject a completed feature vector into the detection queue.
        Used by the simulator to bypass Scapy.
        """
        event = {
            "source": "flow",
            "features": feature_vector,
            "meta": meta,
        }
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._detection_queue.put_nowait, event
            )

    # ── internal ──────────────────────────────────────────────────

    def _reaper(self):
        """Periodically check for expired flows and compute features."""
        while True:
            time.sleep(1)
            now = time.time()
            expired_keys = []
            with self._lock:
                for key, last in list(self._last_seen.items()):
                    if now - last >= FLOW_TIMEOUT:
                        expired_keys.append(key)
            for key in expired_keys:
                with self._lock:
                    packets = self._flows.pop(key, [])
                    self._last_seen.pop(key, None)
                if packets:
                    self._finalize_flow(key, packets)

    def _finalize_flow(self, key: tuple, packets: List[dict]):
        """Compute 19-feature vector and push into detection queue."""
        # Skip micro-flows — too few packets to classify reliably and they
        # produce astronomically high pps values (division by near-zero duration).
        if len(packets) < MIN_FLOW_PACKETS:
            return
        features = self._compute_features(packets)
        meta = {
            "src_ip": key[0],
            "dst_ip": key[1],
            "src_port": key[2],
            "dst_port": key[3],
            "proto": key[4],
        }
        event = {
            "source": "flow",
            "features": features,
            "meta": meta,
        }
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(
                    self._detection_queue.put_nowait, event
                )
            except Exception as exc:
                logger.debug(f"Queue put error: {exc}")

    @staticmethod
    def _compute_features(packets: List[dict]) -> np.ndarray:
        """
        Compute the 19-feature vector. Order is PERMANENT — never change it.

         0  flow_duration
         1  total_fwd_packets
         2  total_backward_packets
         3  flow_bytes_per_s
         4  flow_packets_per_s
         5  packet_length_mean
         6  packet_length_std
         7  packet_length_variance
         8  syn_flag_count
         9  ack_flag_count
        10  rst_flag_count
        11  psh_flag_count
        12  urg_flag_count
        13  average_packet_size        (same as packet_length_mean)
        14  down_per_up_ratio
        15  fwd_packets_per_s
        16  bwd_packets_per_s
        17  active_mean                (placeholder 0.0)
        18  idle_mean                  (placeholder 0.0)
        """
        timestamps = [p["timestamp"] for p in packets]
        sizes = [p["size"] for p in packets]
        fwd = [p for p in packets if p["direction"] == "fwd"]
        bwd = [p for p in packets if p["direction"] == "bwd"]
        total = len(packets)

        flow_duration = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 1e-6
        if flow_duration < MIN_FLOW_DURATION:
            flow_duration = MIN_FLOW_DURATION

        total_fwd = len(fwd)
        total_bwd = len(bwd)

        sum_sizes = sum(sizes) if sizes else 0
        flow_bytes_per_s = sum_sizes / flow_duration
        flow_packets_per_s = total / flow_duration

        pkt_mean = float(np.mean(sizes)) if sizes else 0.0
        pkt_std = float(np.std(sizes)) if sizes else 0.0
        pkt_var = pkt_std ** 2

        syn_count = sum(p["syn"] for p in packets)
        ack_count = sum(p["ack"] for p in packets)
        rst_count = sum(p["rst"] for p in packets)
        psh_count = sum(p["psh"] for p in packets)
        urg_count = sum(p["urg"] for p in packets)

        fwd_sizes = sum(p["size"] for p in fwd) if fwd else 0
        bwd_sizes = sum(p["size"] for p in bwd) if bwd else 0
        down_up = bwd_sizes / fwd_sizes if fwd_sizes > 0 else 0.0

        fwd_pps = total_fwd / flow_duration
        bwd_pps = total_bwd / flow_duration

        vec = np.array([
            flow_duration,        # 0
            total_fwd,            # 1
            total_bwd,            # 2
            flow_bytes_per_s,     # 3
            flow_packets_per_s,   # 4
            pkt_mean,             # 5
            pkt_std,              # 6
            pkt_var,              # 7
            syn_count,            # 8
            ack_count,            # 9
            rst_count,            # 10
            psh_count,            # 11
            urg_count,            # 12
            pkt_mean,             # 13  average_packet_size == packet_length_mean
            down_up,              # 14
            fwd_pps,              # 15
            bwd_pps,              # 16
            0.0,                  # 17  active_mean (placeholder)
            0.0,                  # 18  idle_mean   (placeholder)
        ], dtype=np.float32)

        # Safety: replace any NaN or inf with 0.0
        vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
        return vec
