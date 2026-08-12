"""
ids/geo.py — IP geolocation with caching.
Uses ipinfo.io API for public IPs.
"""

import time
import ipaddress
import logging
import requests

logger = logging.getLogger("ids.geo")

# Cache: { ip_str: (result_dict, expiry_timestamp) }
_cache: dict = {}
CACHE_TTL = 3600  # 1 hour

PRIVATE_RESULT_TEMPLATE = {
    "lat": 0.0,
    "lon": 0.0,
    "city": "Local Network",
    "region": "",
    "country": "Internal",
    "org": "Private",
}


def _is_private(ip_str: str) -> bool:
    """Check if an IP address is private/reserved."""
    try:
        return ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return True  # Treat unparseable IPs as private


def lookup(ip_str: str, token: str = "") -> dict:
    """
    Resolve an IP to geographic coordinates.
    Returns dict: { ip, lat, lon, city, region, country, org }
    Private IPs get a placeholder — never call ipinfo.io for them.
    """
    # Private IP shortcut
    if _is_private(ip_str):
        return {"ip": ip_str, **PRIVATE_RESULT_TEMPLATE}

    # Check cache
    cached = _cache.get(ip_str)
    if cached and cached[1] > time.time():
        return cached[0]

    # Call ipinfo.io
    result = _fetch(ip_str, token)
    _cache[ip_str] = (result, time.time() + CACHE_TTL)
    return result


def _fetch(ip_str: str, token: str) -> dict:
    """Make the HTTP request to ipinfo.io."""
    url = f"https://ipinfo.io/{ip_str}"
    params = {}
    if token:
        params["token"] = token

    try:
        resp = requests.get(url, params=params, timeout=2)
        if resp.status_code != 200:
            logger.warning(f"ipinfo.io returned {resp.status_code} for {ip_str}")
            return {"ip": ip_str, **PRIVATE_RESULT_TEMPLATE}

        data = resp.json()
        loc = data.get("loc", "0.0,0.0")
        parts = loc.split(",")
        lat = float(parts[0]) if len(parts) >= 2 else 0.0
        lon = float(parts[1]) if len(parts) >= 2 else 0.0

        return {
            "ip": ip_str,
            "lat": lat,
            "lon": lon,
            "city": data.get("city", "Unknown"),
            "region": data.get("region", ""),
            "country": data.get("country", "Unknown"),
            "org": data.get("org", "Unknown"),
        }

    except requests.Timeout:
        logger.warning(f"ipinfo.io timeout for {ip_str}")
        return {"ip": ip_str, **PRIVATE_RESULT_TEMPLATE}
    except Exception as exc:
        logger.warning(f"Geo lookup failed for {ip_str}: {exc}")
        return {"ip": ip_str, **PRIVATE_RESULT_TEMPLATE}
