"""
Ship Tracker Agent — reads latest snapshot from the maritime ship-tracking
SQLite database (../ship/ship_tracking.db) and returns vessel counts by
cargo category and port for embedding in the crude oil dashboard.

Falls back gracefully when the database is unavailable (CI / GitHub Actions).
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

# Configurable path — override via env var SHIP_DB_PATH
_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "..", "ship", "ship_tracking.db")
SHIP_DB_PATH = os.environ.get("SHIP_DB_PATH", _DEFAULT_DB)

# Consider data stale if the aggregated_stats row is older than this
STALE_HOURS = 12


def _is_fresh(ts_str: str) -> bool:
    """Return True if the timestamp string (ISO-8601) is within STALE_HOURS."""
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts < timedelta(hours=STALE_HOURS)
    except Exception:
        return False


def get_ship_data() -> dict:
    """
    Return a dict with ship tracking snapshot:
      {
        "available": True/False,
        "stale": True/False,
        "as_of": "30 May 2026, 10:30 AM IST",
        "inbound_count": 12,
        "outbound_count": 5,
        "in_port_count": 8,
        "crude_count": 7,
        "lng_count": 2,
        "cng_count": 1,
        "petroleum_count": 5,
        "busiest_port": "Vadinar",
        "port_activity": [{"port": "Mundra", "count": 3}, ...]
      }
    On failure returns {"available": False, "reason": "..."}.
    """
    db_path = os.path.abspath(SHIP_DB_PATH)
    if not os.path.exists(db_path):
        return {"available": False, "reason": "database not found"}

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # --- Latest aggregated stats row ---
        cur.execute(
            "SELECT * FROM aggregated_stats ORDER BY computed_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            con.close()
            return {"available": False, "reason": "no aggregated stats yet"}

        ts_str = row["computed_at"]
        stale = not _is_fresh(ts_str)

        # Pretty-format timestamp to IST
        try:
            ts_dt = datetime.fromisoformat(ts_str)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            ist = ts_dt + timedelta(hours=5, minutes=30)
            as_of = ist.strftime("%d %b %Y, %I:%M %p IST")
        except Exception:
            as_of = ts_str

        # Parse extra detail from stats_json if available
        extra = {}
        try:
            extra = json.loads(row["stats_json"] or "{}")
        except Exception:
            pass

        result = {
            "available": True,
            "stale": stale,
            "as_of": as_of,
            "inbound_count":   row["total_inbound"],
            "outbound_count":  row["total_outbound"],
            "in_port_count":   row["total_in_port"],
            "crude_count":     row["crude_count"],
            "lng_count":       row["lng_count"],
            "cng_count":       row["cng_count"],
            "petroleum_count": row["petroleum_count"],
            "busiest_port":    row["busiest_port"] or "—",
            "arriving_next_24h": extra.get("arriving_next_24h", 0),
        }

        # --- Port activity breakdown ---
        cur.execute(
            """SELECT port_name, COUNT(*) AS cnt
               FROM port_activity
               GROUP BY port_name
               ORDER BY cnt DESC
               LIMIT 10"""
        )
        result["port_activity"] = [
            {"port": r["port_name"], "count": r["cnt"]} for r in cur.fetchall()
        ]

        con.close()
        return result

    except sqlite3.OperationalError as e:
        return {"available": False, "reason": f"sqlite error: {e}"}
    except Exception as e:
        return {"available": False, "reason": f"unexpected error: {e}"}


if __name__ == "__main__":
    print(json.dumps(get_ship_data(), indent=2))
