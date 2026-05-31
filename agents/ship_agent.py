"""
Ship Tracker Agent — fetches the latest snapshot from the ship dashboard's
publicly published ships_data.json (GitHub Pages) and returns vessel counts
for embedding in the crude oil dashboard.

Works in GitHub Actions with no local DB required.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

SHIPS_JSON_URL = "https://sushobhanpatankar.github.io/ship/ships_data.json"
STALE_HOURS = 2   # treat data as stale if older than this


def _is_fresh(ts_utc: str) -> bool:
    try:
        ts = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
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
        "berthed_count": 5,
        "anchored_count": 3,
        "in_port_count": 12,
        "crude_count": 7,
        "lng_count": 2,
        "cng_count": 1,
        "petroleum_count": 5,
        "busiest_port": "Mundra",
        "port_activity": [{"port": "Mundra", "count": 6}, ...]
      }
    On failure returns {"available": False, "reason": "..."}.
    """
    try:
        req = urllib.request.Request(
            SHIPS_JSON_URL,
            headers={"User-Agent": "crude-dashboard/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"available": False, "reason": f"fetch error: {e}"}
    except Exception as e:
        return {"available": False, "reason": f"unexpected error: {e}"}

    history = data.get("history", [])
    if not history:
        return {"available": False, "reason": "no history in snapshot"}

    latest = history[-1]
    ts_utc = latest.get("ts_utc", "")
    stale = not _is_fresh(ts_utc)

    # Pretty-format timestamp to IST
    try:
        ts_dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        ist = ts_dt + timedelta(hours=5, minutes=30)
        as_of = ist.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        as_of = ts_utc

    port_activity = [
        {"port": port, "count": count}
        for port, count in sorted(
            latest.get("ports", {}).items(), key=lambda x: -x[1]
        )
    ]

    return {
        "available":       True,
        "stale":           stale,
        "as_of":           as_of,
        "berthed_count":   latest.get("berthed", 0),
        "anchored_count":  latest.get("anchored", 0),
        "in_port_count":   latest.get("total_in_port", 0),
        "crude_count":     latest.get("crude", 0),
        "lng_count":       latest.get("lng", 0),
        "cng_count":       latest.get("cng", 0),
        "petroleum_count": latest.get("petroleum", 0),
        "busiest_port":    latest.get("busiest_port") or "—",
        "port_activity":   port_activity,
    }


if __name__ == "__main__":
    print(json.dumps(get_ship_data(), indent=2))
