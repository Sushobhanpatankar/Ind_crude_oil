"""
Flask application — Indian Crude Oil Cost Dashboard
Routes: GET /  |  GET /api/data  |  POST /api/refresh
"""

from datetime import datetime, timezone
from flask import Flask, jsonify, render_template

from agents import get_all_data

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-process cache (simple dict — safe for single-threaded dev server)
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 3600  # 1 hour; RBI rate updates once daily

_cache = {
    "data": None,
    "fetched_at": None,
}


def _is_cache_fresh() -> bool:
    if _cache["data"] is None or _cache["fetched_at"] is None:
        return False
    age = (datetime.now(timezone.utc) - _cache["fetched_at"]).total_seconds()
    return age < CACHE_TTL_SECONDS


def _fetch_and_cache() -> dict:
    now = datetime.now(timezone.utc)
    data = get_all_data()
    data["fetched_at"] = now.isoformat()
    _cache["data"] = data
    _cache["fetched_at"] = now
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    """Serve the dashboard shell — JS fetches data via /api/data."""
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    """Return JSON with crude price, FX rate, and calculated INR price."""
    if not _is_cache_fresh():
        _fetch_and_cache()

    data = dict(_cache["data"])
    age = int((datetime.now(timezone.utc) - _cache["fetched_at"]).total_seconds())
    data["cache_age_seconds"] = age
    return jsonify(data)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Force-clear the cache; next /api/data call will fetch fresh data."""
    _cache["data"] = None
    _cache["fetched_at"] = None
    return jsonify({"status": "cache cleared"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
