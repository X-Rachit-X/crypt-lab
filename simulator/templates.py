"""
simulator/templates.py — Pre-built attack scenario definitions.
Each scenario provides feature vectors and/or log lines that match
the statistical patterns the ML model was trained on (CIC-IDS2017).

Feature order (19 features):
  0  flow_duration (seconds)    10 rst_flag_count
  1  total_fwd_packets           11 psh_flag_count
  2  total_backward_packets      12 urg_flag_count
  3  flow_bytes_per_s            13 average_packet_size
  4  flow_packets_per_s          14 down_per_up_ratio
  5  packet_length_mean          15 fwd_packets_per_s
  6  packet_length_std           16 bwd_packets_per_s
  7  packet_length_variance      17 active_mean
  8  syn_flag_count              18 idle_mean
  9  ack_flag_count

Rule triggers (engine.py):
  - fwd_pps > 10000               → DoS/DDoS
  - rst > 50 AND fwd_pps > 500    → Brute Force
  - rst > 30 AND fwd_pkt > 100 AND pkt_mean < 120  → Port Scan
  - syn > 100 AND ack < 20 AND rst < 30 → DoS
  - pkt_mean > 1500 AND urg > 1   → Heartbleed
  - bytes_ps > 5_000_000          → DDoS
"""

import numpy as np

# ── Scenario Definitions ──────────────────────────────────────────

SCENARIOS = {
    "PORT_SCAN": {
        "name": "Port Scan",
        "description": "Systematic TCP SYN port enumeration from known Tor exit node",
        "expected_label": "Port Scan",
        "expected_seconds": 5,
        "flows": [
            {
                "meta": {
                    "src_ip": "185.220.101.45",
                    "dst_ip": "192.168.1.100",
                    "src_port": 54321,
                    "dst_port": 80,
                    "proto": 6,
                },
                # Port scan: slow methodical probing (pps~150), many SYN+RST pairs
                # small packets (SYN=40 bytes), very few backward (mostly rejected)
                "features": np.array([
                    2000000,   # 0  flow_duration (2s)
                    300,       # 1  total_fwd_packets
                    8,         # 2  total_backward_packets (mostly no response)
                    18000.0,   # 3  flow_bytes_per_s
                    154.0,     # 4  flow_packets_per_s
                    50.0,      # 5  packet_length_mean (SYN packets = ~40-60 bytes)
                    5.0,       # 6  packet_length_std
                    25.0,      # 7  packet_length_variance
                    200,       # 8  syn_flag_count (one SYN per port probed)
                    5,         # 9  ack_flag_count (very few)
                    180,       # 10 rst_flag_count (closed port responses)
                    0,         # 11 psh_flag_count
                    0,         # 12 urg_flag_count
                    50.0,      # 13 average_packet_size
                    0.027,     # 14 down_per_up_ratio (very little backward)
                    150.0,     # 15 fwd_packets_per_s
                    4.0,       # 16 bwd_packets_per_s
                    0.0,       # 17 active_mean
                    0.0,       # 18 idle_mean
                ], dtype=np.float32),
            }
        ],
        "log_lines": [],
    },

    "DOS_FLOOD": {
        "name": "DoS Flood",
        "description": "SYN flood — high-rate single-source denial-of-service",
        "expected_label": "DoS",
        "expected_seconds": 3,
        "flows": [
            {
                "meta": {
                    "src_ip": "91.108.4.1",
                    "dst_ip": "192.168.1.100",
                    "src_port": 12345,
                    "dst_port": 443,
                    "proto": 6,
                },
                # DoS SYN flood: extremely many SYN packets, almost no ACK or RST
                # server is overwhelmed — no RST because server can't respond
                "features": np.array([
                    1000000,    # 0  flow_duration (1s)
                    5000,       # 1  total_fwd_packets
                    10,         # 2  total_backward_packets
                    500000.0,   # 3  flow_bytes_per_s
                    5010.0,     # 4  flow_packets_per_s
                    60.0,       # 5  packet_length_mean
                    10.0,       # 6  packet_length_std
                    100.0,      # 7  packet_length_variance
                    4980,       # 8  syn_flag_count (nearly all SYN)
                    10,         # 9  ack_flag_count (almost none)
                    0,          # 10 rst_flag_count (server overwhelmed, no RST)
                    0,          # 11 psh_flag_count
                    0,          # 12 urg_flag_count
                    60.0,       # 13 average_packet_size
                    0.002,      # 14 down_per_up_ratio
                    5000.0,     # 15 fwd_packets_per_s
                    10.0,       # 16 bwd_packets_per_s
                    0.0,        # 17 active_mean
                    0.0,        # 18 idle_mean
                ], dtype=np.float32),
            }
        ],
        "log_lines": [],
    },

    "BRUTE_FORCE_SSH": {
        "name": "Brute Force SSH",
        "description": "50 failed SSH login attempts + flow-level brute force pattern",
        "expected_label": "Brute Force",
        "expected_seconds": 5,
        "flows": [
            {
                "meta": {
                    "src_ip": "218.92.0.1",
                    "dst_ip": "192.168.1.100",
                    "src_port": 54000,
                    "dst_port": 22,
                    "proto": 6,
                },
                # Brute Force: high-rate attempts (pps~1733), each attempt causes RST
                # many fwd packets, RST-heavy (auth rejected = TCP RST)
                "features": np.array([
                    300000,     # 0  flow_duration (0.3s)
                    500,        # 1  total_fwd_packets
                    20,         # 2  total_backward_packets
                    300000.0,   # 3  flow_bytes_per_s
                    1733.0,     # 4  flow_packets_per_s (fast rate)
                    80.0,       # 5  packet_length_mean (SSH auth pkts, slightly bigger than scan)
                    15.0,       # 6  packet_length_std
                    225.0,      # 7  packet_length_variance
                    0,          # 8  syn_flag_count
                    20,         # 9  ack_flag_count
                    400,        # 10 rst_flag_count (auth rejected = RST)
                    20,         # 11 psh_flag_count
                    0,          # 12 urg_flag_count
                    80.0,       # 13 average_packet_size
                    0.04,       # 14 down_per_up_ratio
                    1667.0,     # 15 fwd_packets_per_s
                    67.0,       # 16 bwd_packets_per_s
                    0.0,        # 17 active_mean
                    0.0,        # 18 idle_mean
                ], dtype=np.float32),
            }
        ],
        "log_lines": [
            f"Failed password for root from 218.92.0.1 port {32000 + i} ssh2"
            for i in range(50)
        ],
        "log_src_ip": "218.92.0.1",
    },

    "WEB_SCAN": {
        "name": "Web Scan",
        "description": "HTTP directory enumeration — 50 × 404 requests",
        "expected_label": "Web Attack",
        "expected_seconds": 5,
        "flows": [],
        "log_lines": [
            f'104.21.0.1 - - [01/Jan/2025:00:00:{i:02d} +0000] "GET /admin{i} HTTP/1.1" 404 162'
            for i in range(50)
        ],
        "log_src_ip": "104.21.0.1",
    },

    "DDOS": {
        "name": "DDoS",
        "description": "5 simultaneous high-bandwidth flows from multiple sources",
        "expected_label": "DDoS",
        "expected_seconds": 8,
        "flows": [
            {
                "meta": {
                    "src_ip": src_ip,
                    "dst_ip": "192.168.1.100",
                    "src_port": 40000 + idx,
                    "dst_port": 80,
                    "proto": 17,  # UDP flood
                },
                # DDoS: very high bandwidth, large packet sizes, minimal backward
                # bytes_ps > 5_000_000 → triggers high-bandwidth rule
                "features": np.array([
                    200000,     # 0  flow_duration (0.2s)
                    400,        # 1  total_fwd_packets
                    50,         # 2  total_backward_packets (> 10 → DDoS not DoS)
                    8000000.0,  # 3  flow_bytes_per_s (> 5MB/s rule trigger)
                    2250.0,     # 4  flow_packets_per_s
                    2000.0,     # 5  packet_length_mean (large UDP payloads)
                    1500.0,     # 6  packet_length_std
                    2250000.0,  # 7  packet_length_variance
                    0,          # 8  syn_flag_count (UDP — no TCP flags)
                    1,          # 9  ack_flag_count
                    0,          # 10 rst_flag_count
                    400,        # 11 psh_flag_count
                    0,          # 12 urg_flag_count
                    2000.0,     # 13 average_packet_size
                    0.125,      # 14 down_per_up_ratio
                    2000.0,     # 15 fwd_packets_per_s
                    250.0,      # 16 bwd_packets_per_s
                    0.0,        # 17 active_mean
                    0.0,        # 18 idle_mean
                ], dtype=np.float32),
            }
            for idx, src_ip in enumerate([
                "185.220.101.45",
                "91.108.4.1",
                "218.92.0.1",
                "104.21.0.1",
                "45.33.32.156",
            ])
        ],
        "log_lines": [],
    },
}

# ── Heartbleed scenario (separate — added after main dict) ───────
SCENARIOS["HEARTBLEED"] = {
    "name": "Heartbleed",
    "description": "CVE-2014-0160 — malformed TLS heartbeat to leak server memory",
    "expected_label": "Heartbleed",
    "expected_seconds": 4,
    "flows": [
        {
            "meta": {
                "src_ip": "45.33.32.156",
                "dst_ip": "192.168.1.100",
                "src_port": 48512,
                "dst_port": 443,
                "proto": 6,
            },
            # Heartbleed: very large packet sizes (oversized heartbeat payloads),
            # URG flags set, few packets, long connection duration
            # Triggers engine rule: pkt_mean > 1500 AND urg > 1
            "features": np.array([
                18000000,   # 0  flow_duration (18s — slow persistent connection)
                4,          # 1  total_fwd_packets (few packets)
                5,          # 2  total_backward_packets (server leaks memory in response)
                30000.0,    # 3  flow_bytes_per_s (low rate, big packets)
                0.5,        # 4  flow_packets_per_s
                1800.0,     # 5  packet_length_mean (oversized heartbeat = 1800+ bytes)
                2200.0,     # 6  packet_length_std (high variance: small req, huge resp)
                4840000.0,  # 7  packet_length_variance
                0,          # 8  syn_flag_count
                5,          # 9  ack_flag_count
                0,          # 10 rst_flag_count
                0,          # 11 psh_flag_count
                3,          # 12 urg_flag_count (malformed TLS = URG set)
                1800.0,     # 13 average_packet_size
                1.25,       # 14 down_per_up_ratio (more data comes back than sent)
                0.22,       # 15 fwd_packets_per_s
                0.28,       # 16 bwd_packets_per_s
                0.0,        # 17 active_mean
                0.0,        # 18 idle_mean
            ], dtype=np.float32),
        }
    ],
    "log_lines": [],
}
