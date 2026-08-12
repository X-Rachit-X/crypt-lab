"""
ids/llm.py — Generate human-readable alert intelligence using Gemini.
Called only when is_attack == True.
"""

import json
import time
import asyncio
import logging
from google import genai
from google.genai import types as genai_types

logger = logging.getLogger("ids.llm")

# ── Caching & Rate Limiting ──────────────────────────────────────
# Cache: keyed on (attack_type, src_ip), TTL = 60s
_cache: dict = {}  # (attack_type, src_ip) -> (result, expiry)

# Token bucket: max 10 calls per minute
_bucket_tokens = 10
_bucket_max = 10
_bucket_last_refill = time.time()
_bucket_lock = asyncio.Lock()


async def _acquire_token() -> bool:
    global _bucket_tokens, _bucket_last_refill
    async with _bucket_lock:
        now = time.time()
        elapsed = now - _bucket_last_refill
        refill = elapsed * (_bucket_max / 60.0)
        _bucket_tokens = min(_bucket_max, _bucket_tokens + refill)
        _bucket_last_refill = now
        if _bucket_tokens >= 1:
            _bucket_tokens -= 1
            return True
        return False


PROMPT_TEMPLATE = """You are a cybersecurity expert analyzing a live network intrusion.

Attack Context:
- Type: {attack_type}
- Source: {src_ip} ({geo_city}, {geo_country})
- Target: {dst_ip}:{dst_port}
- Confidence: {confidence:.0%}  |  Severity: {severity}
- Traffic: {flow_packets_per_s:.0f} packets/s, {flow_bytes_per_s:.0f} bytes/s
- SYN flags: {syn_flag_count}  |  Mean packet size: {packet_length_mean:.0f} bytes
- Related log events: {log_events}

Respond ONLY with this JSON structure. No markdown. No extra text.
{{
  "alert_message": "One sentence describing the attack and its risk for a general audience.",
  "technical_summary": "2-3 sentences with technical detail for a security analyst.",
  "countermeasures": [
    "Immediate action 1",
    "Immediate action 2",
    "Preventive action 3",
    "Monitoring action 4"
  ],
  "threat_level_explanation": "One sentence explaining the severity assignment."
}}"""


def _build_fallback(context: dict) -> dict:
    """Return a deterministic fallback when Gemini is unavailable."""
    at = context.get("attack_type", "Unknown")
    ip = context.get("src_ip", "Unknown")
    city = context.get("geo_city", "Unknown")
    country = context.get("geo_country", "Unknown")
    conf = context.get("confidence", 0.0)
    sev = context.get("severity", "Medium")
    return {
        "alert_message": f"{at} detected from {ip} ({city}, {country}) with {conf:.0%} confidence.",
        "technical_summary": f"Automated ML detection flagged suspicious {at} traffic pattern from {ip}.",
        "countermeasures": [
            f"Block {ip} at the perimeter firewall immediately.",
            "Review all traffic from this IP in the past 30 minutes.",
            "Check for lateral movement from this source to other hosts.",
            "Escalate to the security team if the pattern continues.",
        ],
        "threat_level_explanation": f"Classified as {sev} based on attack type and observed traffic volume.",
    }


_STATIC_COUNTERMEASURES: dict[str, dict] = {
    "Port Scan": {
        "alert_message": "Port scan detected — attacker is enumerating open services.",
        "technical_summary": "Sequential or random port probing detected. Attacker is mapping open services for follow-up exploitation.",
        "countermeasures": [
            "Block the source IP at the perimeter firewall.",
            "Enable port-scan detection rules in your IDS/IPS.",
            "Close all unnecessary open ports and services.",
            "Monitor for follow-up connection attempts from this IP.",
        ],
        "threat_level_explanation": "Port scans are reconnaissance — low direct damage but signal imminent attack.",
    },
    "Brute Force": {
        "alert_message": "Brute force login attempt detected — credentials under attack.",
        "technical_summary": "High-frequency authentication failures from a single IP indicate automated credential stuffing or dictionary attack.",
        "countermeasures": [
            "Temporarily block the source IP using fail2ban or firewall rule.",
            "Enforce account lockout after 5 failed attempts.",
            "Enable multi-factor authentication on targeted services.",
            "Audit recent successful logins from this IP for compromise.",
        ],
        "threat_level_explanation": "Brute force attacks risk credential compromise and unauthorized access.",
    },
    "DDoS": {
        "alert_message": "DDoS attack detected — volumetric flood targeting your infrastructure.",
        "technical_summary": "High packet rate with spoofed or distributed sources targeting a single endpoint, causing service degradation.",
        "countermeasures": [
            "Enable rate-limiting and traffic shaping upstream.",
            "Activate DDoS mitigation service (Cloudflare, AWS Shield, etc.).",
            "Null-route the most aggressive source IPs.",
            "Scale up bandwidth or switch to scrubbing centre.",
        ],
        "threat_level_explanation": "DDoS attacks cause availability loss and can mask concurrent intrusion attempts.",
    },
    "DoS": {
        "alert_message": "DoS flood detected from a single source IP.",
        "technical_summary": "Single-source denial-of-service flood consuming server resources and degrading availability.",
        "countermeasures": [
            "Block the attacking IP immediately at the firewall.",
            "Apply SYN cookie protection if SYN flood is confirmed.",
            "Increase connection timeout thresholds to reduce impact.",
            "Alert on CPU/memory spikes caused by the flood.",
        ],
        "threat_level_explanation": "DoS from a single source is easier to mitigate than distributed but still threatens availability.",
    },
    "Web Attack": {
        "alert_message": "Web application attack detected — injection or scanning activity.",
        "technical_summary": "Malicious HTTP payloads detected including SQL injection, XSS, or path traversal attempts against the web application.",
        "countermeasures": [
            "Block the source IP at the WAF immediately.",
            "Review web server access logs for successful exploitation.",
            "Patch application vulnerabilities detected in the requests.",
            "Enable WAF rules for SQLi, XSS, and directory traversal.",
        ],
        "threat_level_explanation": "Web attacks risk data exfiltration, RCE, or defacement if exploited successfully.",
    },
    "Infiltration": {
        "alert_message": "Infiltration/privilege escalation activity detected.",
        "technical_summary": "Post-exploitation behaviour detected: credential reuse, privilege escalation, or lateral movement indicators.",
        "countermeasures": [
            "Isolate the affected host from the network immediately.",
            "Force password reset for all accounts touched by this IP.",
            "Audit sudo/admin logs for unauthorized privilege use.",
            "Run endpoint forensics to identify persistence mechanisms.",
        ],
        "threat_level_explanation": "Infiltration indicates an active breach — immediate containment is critical.",
    },
    "Bot": {
        "alert_message": "Bot activity detected — automated malicious traffic.",
        "technical_summary": "Automated bot traffic pattern detected with consistent timing and payload structure suggesting C2 communication or scraping.",
        "countermeasures": [
            "Block the source IP and its subnet at the firewall.",
            "Check for malware on internal hosts communicating with this IP.",
            "Enable bot-detection rules in your WAF.",
            "Review DNS logs for C2 domain lookups from internal hosts.",
        ],
        "threat_level_explanation": "Bot traffic may indicate C2 communication, data harvesting, or credential abuse.",
    },
    "Heartbleed": {
        "alert_message": "Heartbleed exploit attempt detected against OpenSSL.",
        "technical_summary": "Malformed TLS heartbeat request detected — attacker attempting CVE-2014-0160 memory leak against OpenSSL.",
        "countermeasures": [
            "Immediately upgrade OpenSSL to a patched version (>=1.0.1g).",
            "Block the attacking IP at the firewall.",
            "Rotate all SSL/TLS certificates and private keys.",
            "Audit for any data leaked prior to detection.",
        ],
        "threat_level_explanation": "Heartbleed can leak server memory including private keys and credentials — critical severity.",
    },
}

_STATIC_DEFAULT = {
    "alert_message": "Suspicious network activity detected by the IDS.",
    "technical_summary": "ML model flagged traffic pattern as malicious. Manual review recommended.",
    "countermeasures": [
        "Block the source IP at the perimeter firewall.",
        "Review all traffic from this IP in the past 30 minutes.",
        "Check for lateral movement from this source to other hosts.",
        "Escalate to the security team if the pattern continues.",
    ],
    "threat_level_explanation": "Classified by ML model based on observed traffic features.",
}


def get_static_response(attack_type: str) -> dict:
    """
    Return a pre-written countermeasures dict without any Gemini API call.
    Used for Medium and Low severity alerts to preserve daily quota.
    """
    # Normalise: try exact match first, then partial
    result = _STATIC_COUNTERMEASURES.get(attack_type)
    if result:
        return result
    for key, val in _STATIC_COUNTERMEASURES.items():
        if key.lower() in attack_type.lower() or attack_type.lower() in key.lower():
            return val
    return _STATIC_DEFAULT


async def enrich(context: dict, gemini_model: str = "gemini-1.5-flash") -> dict:
    """
    Call Gemini to generate alert intelligence.
    Returns dict with keys: alert_message, technical_summary, countermeasures,
    threat_level_explanation.
    """
    cache_key = (context.get("attack_type"), context.get("src_ip"))

    # Check cache
    cached = _cache.get(cache_key)
    if cached and cached[1] > time.time():
        return cached[0]

    # Rate limit
    if not await _acquire_token():
        logger.warning("LLM rate limit hit — returning fallback")
        return _build_fallback(context)

    prompt = PROMPT_TEMPLATE.format(
        attack_type=context.get("attack_type", "Unknown"),
        src_ip=context.get("src_ip", "Unknown"),
        geo_city=context.get("geo_city", "Unknown"),
        geo_country=context.get("geo_country", "Unknown"),
        dst_ip=context.get("dst_ip", "Unknown"),
        dst_port=context.get("dst_port", 0),
        confidence=context.get("confidence", 0.0),
        severity=context.get("severity", "Medium"),
        flow_packets_per_s=context.get("flow_packets_per_s", 0.0),
        flow_bytes_per_s=context.get("flow_bytes_per_s", 0.0),
        syn_flag_count=context.get("syn_flag_count", 0),
        packet_length_mean=context.get("packet_length_mean", 0.0),
        log_events=context.get("log_events", []),
    )

    try:
        result = await asyncio.wait_for(
            _call_gemini(prompt, gemini_model), timeout=3.0
        )
        # Cache for 60 seconds
        _cache[cache_key] = (result, time.time() + 60)
        return result
    except asyncio.TimeoutError:
        logger.warning("Gemini timed out — returning fallback")
        return _build_fallback(context)
    except Exception as exc:
        logger.warning(f"Gemini error: {exc} — returning fallback")
        return _build_fallback(context)


async def _call_gemini(prompt: str, model_name: str) -> dict:
    """Offload blocking Gemini call to a thread using the google.genai SDK."""

    def _blocking():
        client = genai.Client()
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return resp.text or ""

    text = await asyncio.to_thread(_blocking)
    return _parse_response(text)


def _parse_response(text: str) -> dict:
    """Parse Gemini JSON output with fallback."""
    if not text:
        return {
            "alert_message": "Analysis unavailable.",
            "technical_summary": "",
            "countermeasures": [],
            "threat_level_explanation": "",
        }
    # Try direct parse
    try:
        data = json.loads(text)
        return _normalize(data)
    except Exception:
        pass
    # Try extracting JSON from text
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            data = json.loads(text[start : end + 1])
            return _normalize(data)
    except Exception:
        pass
    # Raw fallback
    return {
        "alert_message": text.strip()[:200],
        "technical_summary": "",
        "countermeasures": [],
        "threat_level_explanation": "",
    }


def _normalize(data: dict) -> dict:
    return {
        "alert_message": data.get("alert_message", ""),
        "technical_summary": data.get("technical_summary", ""),
        "countermeasures": data.get("countermeasures", []),
        "threat_level_explanation": data.get("threat_level_explanation", ""),
    }
