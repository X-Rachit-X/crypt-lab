"""
ids/alerts.py — Build alert dicts and encrypt with AES-256-GCM.
"""

import os
import json
import uuid
import base64
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ids.alerts")

# Severity mapping
SEVERITY_MAP = {
    "DoS": "High",
    "DDoS": "High",
    "Bot": "High",
    "Heartbleed": "High",
    "Infiltration": "High",
    "Port Scan": "Medium",
    "Brute Force": "Medium",
    "Web Attack": "Medium",
}


def get_severity(attack_type: str) -> str:
    """Return severity level for an attack type."""
    return SEVERITY_MAP.get(attack_type, "Low")


def build_alert(
    detection: dict,
    geo: dict,
    llm: dict,
    meta: dict,
    related_logs: list = None,
) -> dict:
    """
    Assemble the complete alert dict from detection, geo, LLM, and metadata.
    """
    return {
        # Identity
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Detection
        "attack_type": detection.get("label", "Unknown"),
        "confidence": detection.get("confidence", 0.0),
        "severity": get_severity(detection.get("label", "Unknown")),
        "source": detection.get("source", "unknown"),
        # Network
        "src_ip": meta.get("src_ip", "0.0.0.0"),
        "dst_ip": meta.get("dst_ip", "0.0.0.0"),
        "src_port": meta.get("src_port", 0),
        "dst_port": meta.get("dst_port", 0),
        "protocol": meta.get("proto", 0),
        # Geo
        "geo_lat": geo.get("lat", 0.0),
        "geo_lon": geo.get("lon", 0.0),
        "geo_city": geo.get("city", "Unknown"),
        "geo_country": geo.get("country", "Unknown"),
        "geo_org": geo.get("org", "Unknown"),
        # LLM
        "alert_message": llm.get("alert_message", ""),
        "technical_summary": llm.get("technical_summary", ""),
        "countermeasures": llm.get("countermeasures", []),
        "threat_level_explanation": llm.get("threat_level_explanation", ""),
        # Logs
        "related_logs": related_logs or [],
    }


def encrypt_alert(alert: dict) -> str:
    """
    Encrypt the full alert dict with AES-256-GCM.
    Returns a base64 token of nonce + ciphertext.
    The key MUST come from the IDS_AES_KEY environment variable.
    Returns empty string if no key is configured.
    """
    key_hex = os.environ.get("IDS_AES_KEY", "")
    if not key_hex:
        logger.warning("IDS_AES_KEY not set — storing alert unencrypted")
        return ""

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = bytes.fromhex(key_hex)
        nonce = os.urandom(12)
        plaintext = json.dumps(alert).encode("utf-8")
        ct = AESGCM(key).encrypt(nonce, plaintext, None)
        token = base64.b64encode(nonce + ct).decode("utf-8")
        return token
    except Exception as exc:
        logger.error(f"Encryption failed: {exc}")
        return ""
