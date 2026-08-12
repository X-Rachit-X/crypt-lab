"""
ids/db.py — SQLite storage for alerts.
"""

import json
import sqlite3
import logging
import threading

logger = logging.getLogger("ids.db")

DB_PATH = "ids_alerts.db"
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """Create the alerts table if it does not exist, and prune old records."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id                    TEXT PRIMARY KEY,
            timestamp             TEXT,
            attack_type           TEXT,
            src_ip                TEXT,
            dst_ip                TEXT,
            severity              TEXT,
            confidence            REAL,
            geo_lat               REAL,
            geo_lon               REAL,
            geo_city              TEXT,
            geo_country           TEXT,
            alert_message         TEXT,
            countermeasures       TEXT,
            encrypted_payload     TEXT
        )
    """)
    conn.commit()

    # Auto-rotate: delete alerts older than 7 days to keep DB small
    deleted = conn.execute(
        "DELETE FROM alerts WHERE timestamp < datetime('now', '-7 days')"
    ).rowcount
    conn.commit()
    if deleted:
        logger.info(f"DB rotation: removed {deleted} alerts older than 7 days.")

    logger.info(f"Database initialized: {DB_PATH}")


def store_alert(alert: dict, encrypted: str):
    """Insert a single alert into the database. Uses INSERT OR IGNORE."""
    conn = _get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO alerts
           (id, timestamp, attack_type, src_ip, dst_ip, severity,
            confidence, geo_lat, geo_lon, geo_city, geo_country,
            alert_message, countermeasures, encrypted_payload)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            alert["id"],
            alert["timestamp"],
            alert["attack_type"],
            alert["src_ip"],
            alert["dst_ip"],
            alert["severity"],
            alert["confidence"],
            alert["geo_lat"],
            alert["geo_lon"],
            alert["geo_city"],
            alert["geo_country"],
            alert["alert_message"],
            json.dumps(alert.get("countermeasures", [])),
            encrypted,
        ),
    )
    conn.commit()


def fetch_alerts(limit: int = 50) -> list:
    """Return the last *limit* alerts, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        # Parse countermeasures back to list
        try:
            d["countermeasures"] = json.loads(d.get("countermeasures", "[]"))
        except Exception:
            d["countermeasures"] = []
        results.append(d)
    return results


def fetch_stats() -> dict:
    """Return { attack_type: count } for the chart."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT attack_type, COUNT(*) as cnt FROM alerts GROUP BY attack_type"
    ).fetchall()
    return {row["attack_type"]: row["cnt"] for row in rows}


def fetch_map_data() -> list:
    """Return list of dicts for Leaflet map markers."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT src_ip, geo_lat, geo_lon, geo_city, geo_country,
                  attack_type, severity, timestamp, alert_message
           FROM alerts
           WHERE geo_lat != 0.0 OR geo_lon != 0.0
           ORDER BY timestamp DESC
           LIMIT 200"""
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_countermeasures() -> list:
    """Return countermeasures from the most recent High or Medium alert."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT countermeasures FROM alerts
           WHERE severity IN ('High', 'Medium')
           ORDER BY timestamp DESC LIMIT 1"""
    ).fetchone()
    if row:
        try:
            return json.loads(row["countermeasures"])
        except Exception:
            return []
    return []


def fetch_top_ips(limit: int = 10) -> list:
    """Return [{ src_ip, count, last_attack, attack_types }] sorted by count desc."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT src_ip,
                  COUNT(*) as cnt,
                  MAX(timestamp) as last_seen,
                  GROUP_CONCAT(DISTINCT attack_type) as types
           FROM alerts
           WHERE src_ip IS NOT NULL AND src_ip != '0.0.0.0'
           GROUP BY src_ip
           ORDER BY cnt DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [
        {
            "src_ip": r["src_ip"],
            "count": r["cnt"],
            "last_seen": r["last_seen"],
            "attack_types": r["types"].split(",") if r["types"] else [],
        }
        for r in rows
    ]


def fetch_hourly_counts(hours: int = 24) -> list:
    """Return [{ hour, count }] for the last *hours* hours, oldest first."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT strftime('%Y-%m-%dT%H:00', timestamp) as hour,
                  COUNT(*) as cnt
           FROM alerts
           WHERE timestamp >= datetime('now', ? || ' hours')
           GROUP BY hour
           ORDER BY hour ASC""",
        (f"-{hours}",),
    ).fetchall()
    return [{"hour": r["hour"], "count": r["cnt"]} for r in rows]


def fetch_severity_counts() -> dict:
    """Return { High: n, Medium: n, Low: n } totals."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT severity, COUNT(*) as cnt FROM alerts GROUP BY severity"
    ).fetchall()
    result = {"High": 0, "Medium": 0, "Low": 0}
    for r in rows:
        if r["severity"] in result:
            result[r["severity"]] = r["cnt"]
    return result


def clear_alerts() -> None:
    """Delete all alerts from the database."""
    conn = _get_conn()
    conn.execute("DELETE FROM alerts")
    conn.commit()
