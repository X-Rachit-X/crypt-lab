"""
simulator/simulator.py — Inject fake attack events into the IDS pipeline.
Bypasses Scapy entirely — injects feature vectors and log events directly
into the internal queues. Works without network access.
"""

import time
import asyncio
import logging

logger = logging.getLogger("simulator")


async def run_scenario(scenario: dict, aggregator, detection_queue, loop=None):
    """
    Execute a simulation scenario by injecting flows and/or log lines
    into the IDS pipeline.

    *scenario*: one of the dicts from templates.SCENARIOS
    *aggregator*: FlowAggregator instance (for flow injection)
    *detection_queue*: asyncio.Queue for log events
    """
    name = scenario.get("name", "Unknown")
    logger.info(f"Simulator: starting scenario '{name}'")

    # Inject flow-based events
    flows = scenario.get("flows", [])
    for flow in flows:
        features = flow["features"]
        meta = flow["meta"]
        aggregator.inject_flow(features, meta)
        await asyncio.sleep(0.05)  # small stagger

    # Inject log-based events
    log_lines = scenario.get("log_lines", [])
    log_src_ip = scenario.get("log_src_ip")
    for line in log_lines:
        event = {
            "source": "log",
            "timestamp": time.time(),
            "log_file": "/var/log/auth.log",
            "raw_line": line,
            "log_type": "auth_failure",
            "src_ip": log_src_ip,
            "severity": "High",
        }
        # For web scan lines, adjust type
        if "404" in line:
            event["log_type"] = "http_scan"
            event["severity"] = "Medium"
            event["log_file"] = "/var/log/nginx/access.log"

        try:
            detection_queue.put_nowait(event)
        except Exception:
            pass

        # Also add to the shared log lines for the live viewer
        try:
            from ids import _recent_log_lines
            _recent_log_lines.append({
                "timestamp": time.time(),
                "log_file": event["log_file"],
                "raw_line": line,
                "log_type": event["log_type"],
                "severity": event["severity"],
            })
            while len(_recent_log_lines) > 500:
                _recent_log_lines.pop(0)
        except Exception:
            pass

        await asyncio.sleep(0.02)  # stagger log injection

    logger.info(f"Simulator: scenario '{name}' injection complete")
