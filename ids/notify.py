"""
ids/notify.py — Telegram notifications for High severity IDS alerts.

Setup:
  1. Create a bot via @BotFather on Telegram → get TELEGRAM_BOT_TOKEN
  2. Send any message to your bot, then get your chat ID:
       curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
  3. Add to .env:
       TELEGRAM_BOT_TOKEN=123456:ABCdef...
       TELEGRAM_CHAT_ID=987654321

The notifier fires once per unique (src_ip + attack_type) per hour so
it doesn't spam you during a sustained attack.
"""

import time
import logging
import threading
import requests

logger = logging.getLogger("ids.notify")

# Dedup: don't notify the same IP+attack more than once per hour
_notified: dict[str, float] = {}
_lock = threading.Lock()
NOTIFY_COOLDOWN = 3600  # 1 hour


def _send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send a message via the Telegram Bot API. Returns True on success."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        if resp.status_code == 200:
            return True
        logger.warning(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
        return False
    except requests.RequestException as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def notify(alert: dict, token: str, chat_id: str):
    """
    Send a Telegram notification for a High or Medium severity alert.
    Safe to call from any thread — uses its own lock for dedup.
    Runs the HTTP request in a background thread so it never blocks the detection loop.
    """
    if not token or not chat_id:
        return  # Not configured — silently skip

    src_ip = alert.get("src_ip", "?")
    attack_type = alert.get("attack_type", "Unknown")
    severity = alert.get("severity", "Medium")

    # Only notify for High and Medium
    if severity not in ("High", "Medium"):
        return

    # Deduplication
    dedup_key = f"{src_ip}:{attack_type}"
    now = time.time()
    with _lock:
        if now - _notified.get(dedup_key, 0) < NOTIFY_COOLDOWN:
            return
        _notified[dedup_key] = now

    # Build message
    geo_city = alert.get("geo_city") or "Unknown"
    geo_country = alert.get("geo_country") or "?"
    confidence = int((alert.get("confidence") or 0) * 100)
    location = f"{geo_city}, {geo_country}" if geo_city not in ("Unknown", "Local Network") else "Local Network"

    severity_icon = "🔴" if severity == "High" else "🟡"

    cms = alert.get("countermeasures") or []
    cms_text = ""
    if cms:
        cms_text = "\n\n<b>Countermeasures:</b>\n" + "\n".join(
            f"  {i+1}. {c}" for i, c in enumerate(cms[:3])
        )

    message = (
        f"{severity_icon} <b>Crypt Lab IDS Alert</b>\n\n"
        f"<b>Attack:</b> {attack_type}\n"
        f"<b>Severity:</b> {severity}\n"
        f"<b>Source IP:</b> <code>{src_ip}</code>\n"
        f"<b>Location:</b> {location}\n"
        f"<b>Confidence:</b> {confidence}%\n"
        f"<b>Message:</b> {alert.get('alert_message', '')[:120]}"
        f"{cms_text}"
    )

    # Fire-and-forget in a daemon thread — never blocks detection loop
    t = threading.Thread(
        target=_send_telegram,
        args=(token, chat_id, message),
        daemon=True,
    )
    t.start()
    logger.info(f"Telegram notification queued: {severity} {attack_type} from {src_ip}")
