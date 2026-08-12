"""
ids/log_capture.py — Watch system log files for suspicious entries.
Supports Ubuntu systemd ISO 8601 log format and handles log rotation.
"""

import os
import re
import time
import logging
import asyncio
from typing import List

logger = logging.getLogger("ids.log_capture")

IP_RE = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

# ---------------------------------------------------------------------------
# Noise filter — lines matching ANY of these strings are silently skipped.
# This prevents WiFi events, cron, snap, and other system chatter from
# polluting the log viewer with irrelevant entries.
# ---------------------------------------------------------------------------
_NOISE_FRAGMENTS = (
    "wpa_supplicant",
    "CTRL-EVENT-SIGNAL",
    "CTRL-EVENT-SCAN",
    "CTRL-EVENT-CONNECTED",
    "CTRL-EVENT-DISCONNECTED",
    "CTRL-EVENT-REGDOM",
    "WPS-AP-AVAIL",
    "SME: Trying to authenticate",
    "Trying to authenticate",
    "Associated with",
    "EAPOL-KEY",
    "pam_unix(cron:",
    "CRON[",
    "session opened for user root by root",
    "session closed for user root",
    "pam_unix(systemd-user:",
    "pam_loginuid",
    "pam_env(",
    "snap.brave",
    "snap.discord",
    "snap.spotify",
    "NetworkManager[",
    "dhclient[",
    "systemd-resolved",
    "systemd-logind",
    "kernel: audit",
    "dbus-daemon",
    "rtkit-daemon",
    "polkitd",
    "bluetoothd",
    "avahi-daemon",
    "colord",
    "upowerd",
    "ModemManager",
)

# ---------------------------------------------------------------------------
# Attack / anomaly patterns — (compiled_regex, log_type, severity)
# Order matters: more specific patterns first.
# ---------------------------------------------------------------------------
PATTERNS = [
    # ── SSH brute-force / auth failures ────────────────────────────────────
    (re.compile(r"Failed password", re.IGNORECASE),                             "auth_failure",        "High"),
    (re.compile(r"authentication failure",re.IGNORECASE),                       "auth_failure",        "High"),
    (re.compile(r"Invalid user\s+\S+\s+from",re.IGNORECASE),                   "auth_failure",        "High"),
    (re.compile(r"POSSIBLE BREAK-IN ATTEMPT",re.IGNORECASE),                    "auth_failure",        "High"),
    (re.compile(r"Connection closed by authenticating user",re.IGNORECASE),     "auth_failure",        "High"),
    (re.compile(r"too many authentication failures",re.IGNORECASE),             "auth_failure",        "High"),
    (re.compile(r"maximum authentication attempts exceeded",re.IGNORECASE),     "auth_failure",        "High"),
    (re.compile(r"Disconnecting.*preauth",re.IGNORECASE),                       "auth_failure",        "Medium"),
    (re.compile(r"Unable to negotiate.*no matching",re.IGNORECASE),             "auth_failure",        "Medium"),
    # ── SSH successful (informational) ─────────────────────────────────────
    (re.compile(r"Accepted (?:password|publickey)",re.IGNORECASE),              "ssh_success",         "Low"),
    # ── Privilege escalation ───────────────────────────────────────────────
    (re.compile(
        r"sudo:.*COMMAND=.*(?:/bin/su|/usr/bin/passwd|/usr/sbin/adduser|"
        r"/usr/sbin/useradd|/usr/sbin/visudo|/bin/chmod\s+[0-9]*7|"
        r"/usr/bin/chown|/usr/bin/pkexec|/bin/bash|/bin/sh)",
        re.IGNORECASE),                                                          "privilege_escalation","High"),
    (re.compile(r"sudo:.*incorrect password attempt",re.IGNORECASE),            "privilege_escalation","High"),
    (re.compile(r"sudo:.*\bNOT in sudoers\b",re.IGNORECASE),                   "privilege_escalation","High"),
    (re.compile(r"sudo:.*command not allowed",re.IGNORECASE),                   "privilege_escalation","Medium"),
    # ── AppArmor / kernel security violations (kern.log) ──────────────────
    (re.compile(
        r'apparmor="DENIED".*operation="(?:exec|ptrace|mount|file_receive|'
        r'connect|sendmsg|socket|open|mknod|link|rename)"',
        re.IGNORECASE),                                                          "privilege_escalation","Medium"),
    (re.compile(r"kernel:.*SYN.*flood",re.IGNORECASE),                         "auth_failure",        "High"),
    (re.compile(r"kernel:.*Possible SYN flooding",re.IGNORECASE),              "auth_failure",        "High"),
    (re.compile(r"kernel:.*nf_conntrack.*table full",re.IGNORECASE),           "auth_failure",        "High"),
    # ── Web scanning (will also be caught by HTTP burst logic below) ───────
    (re.compile(r'"(?:GET|POST|HEAD|PUT|DELETE|OPTIONS)\s+.*HTTP.*"\s+(?:400|401|403|404|405|429)', re.IGNORECASE),
                                                                                 "http_scan",           "Medium"),
    # ── Suspicious SSH tunnelling / port-forwarding ────────────────────────
    (re.compile(r"error: kex_exchange_identification",re.IGNORECASE),           "auth_failure",        "Medium"),
    (re.compile(r"Did not receive identification string from",re.IGNORECASE),   "auth_failure",        "Medium"),
]

# For HTTP burst detection (per-file counters)
_http_404_times: dict = {}   # path -> [timestamps]
_http_500_times: dict = {}
_http_4xx_times: dict = {}   # catch-all 4xx for web scanning


# ---------------------------------------------------------------------------
# Line classifier
# ---------------------------------------------------------------------------

def _is_noise(line: str) -> bool:
    """Return True if the line is known system chatter that should be ignored."""
    for fragment in _NOISE_FRAGMENTS:
        if fragment in line:
            return True
    return False


def _classify_line(line: str, log_file: str):
    """
    Return (log_type, severity, src_ip) or None if the line is not interesting.
    """
    if _is_noise(line):
        return None

    # Pattern matching
    for pattern, log_type, severity in PATTERNS:
        if pattern.search(line):
            ip_match = IP_RE.search(line)
            src_ip = ip_match.group(1) if ip_match else None
            return log_type, severity, src_ip

    # ── HTTP 404 burst (>20 in 10 s) → web/port scan ──────────────────────
    if " 404 " in line:
        now = time.time()
        times = _http_404_times.setdefault(log_file, [])
        times.append(now)
        _http_404_times[log_file] = [t for t in times if now - t < 10]
        if len(_http_404_times[log_file]) > 20:
            ip_match = IP_RE.search(line)
            _http_404_times[log_file] = []
            return "http_scan", "Medium", ip_match.group(1) if ip_match else None

    # ── HTTP 500 burst (>10 in 10 s) → application abuse ─────────────────
    if " 500 " in line:
        now = time.time()
        times = _http_500_times.setdefault(log_file, [])
        times.append(now)
        _http_500_times[log_file] = [t for t in times if now - t < 10]
        if len(_http_500_times[log_file]) > 10:
            ip_match = IP_RE.search(line)
            _http_500_times[log_file] = []
            return "http_error", "Medium", ip_match.group(1) if ip_match else None

    # ── Generic 4xx burst (>30 in 15 s) → web scanning ───────────────────
    _4xx = re.search(r'" 4\d\d ', line)
    if _4xx:
        now = time.time()
        times = _http_4xx_times.setdefault(log_file, [])
        times.append(now)
        _http_4xx_times[log_file] = [t for t in times if now - t < 15]
        if len(_http_4xx_times[log_file]) > 30:
            ip_match = IP_RE.search(line)
            _http_4xx_times[log_file] = []
            return "http_scan", "Medium", ip_match.group(1) if ip_match else None

    return None


# ---------------------------------------------------------------------------
# File tailer with log-rotation awareness
# ---------------------------------------------------------------------------

def _tail_file(path: str, detection_queue: asyncio.Queue, loop):
    """
    Tail *path* from the current end.  Detects log rotation (inode change or
    file truncation) and re-opens the file automatically so no events are lost
    after logrotate/syslog restart.
    """
    def _open_at_end(p: str):
        fh = open(p, "r", errors="replace")
        fh.seek(0, os.SEEK_END)
        inode = os.fstat(fh.fileno()).st_ino
        return fh, inode

    try:
        fh, current_inode = _open_at_end(path)
    except PermissionError:
        logger.error(f"Permission denied reading {path}. "
                     f"Run as root or add user to 'adm' group.")
        return
    except FileNotFoundError:
        logger.warning(f"Log file not found: {path}. Will retry in 30 s.")
        time.sleep(30)
        try:
            fh, current_inode = _open_at_end(path)
        except Exception as exc:
            logger.error(f"Still cannot open {path}: {exc}")
            return
    except Exception as exc:
        logger.warning(f"Cannot open log file {path}: {exc}")
        return

    logger.info(f"✅ Watching log file: {path}")

    while True:
        line = fh.readline()
        if not line:
            # Check for log rotation: inode changed or file shrank
            try:
                st = os.stat(path)
                if st.st_ino != current_inode or fh.tell() > st.st_size:
                    logger.info(f"Log rotation detected for {path}, reopening.")
                    fh.close()
                    fh, current_inode = _open_at_end(path)
            except FileNotFoundError:
                pass
            time.sleep(0.25)
            continue

        line = line.strip()
        if not line:
            continue

        # Skip pure noise lines entirely — don't send to viewer or queue
        if _is_noise(line):
            continue

        result = _classify_line(line, path)
        if result:
            log_type, severity, src_ip = result
            event = {
                "source": "log",
                "timestamp": time.time(),
                "log_file": path,
                "raw_line": line,
                "log_type": log_type,
                "src_ip": src_ip,
                "severity": severity,
            }
            try:
                loop.call_soon_threadsafe(detection_queue.put_nowait, event)
            except Exception:
                pass

        # Push every non-noise line to the live log viewer
        try:
            from ids import _recent_log_lines
            _recent_log_lines.append({
                "timestamp": time.time(),
                "log_file": path,
                "raw_line": line,
                "log_type": result[0] if result else "generic",
                "severity": result[1] if result else "Low",
            })
            # Cap at 1000 lines
            while len(_recent_log_lines) > 1000:
                _recent_log_lines.pop(0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def start(log_paths: List[str], detection_queue: asyncio.Queue, loop=None):
    """
    Start watching all log files.  Blocks — run in a daemon thread.
    *loop* is the asyncio event loop for thread-safe queue puts.
    """
    import threading

    if loop is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.error("No asyncio event loop available for log_capture.")
            return

    started = 0
    for path in log_paths:
        path = path.strip()
        if not path:
            continue
        t = threading.Thread(
            target=_tail_file,
            args=(path, detection_queue, loop),
            daemon=True,
            name=f"log-watcher:{os.path.basename(path)}",
        )
        t.start()
        started += 1
        logger.info(f"Started log watcher thread for: {path}")

    logger.info(f"Log capture started — watching {started} file(s).")

    # Keep this thread alive
    while True:
        time.sleep(60)
