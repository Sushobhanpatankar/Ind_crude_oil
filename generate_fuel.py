"""
Static site generator — India Fuel Retail Prices dashboard.
Fetches daily petrol/diesel prices from PPAC, appends to docs/fuel_data.json,
writes self-contained docs/fuel.html.
Run by the GitHub Actions workflow every morning at 07:00 IST.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from agents.fuel_agent import get_fuel_prices

HISTORY_FILE = "docs/fuel_data.json"
MAX_HISTORY  = 90   # ~3 months of daily data

CITIES = ["Delhi", "Mumbai", "Chennai"]

CITY_COLORS = {
    "Delhi":   {"petrol": "#f59e0b", "diesel": "#fb923c"},
    "Mumbai":  {"petrol": "#3b82f6", "diesel": "#60a5fa"},
    "Chennai": {"petrol": "#10b981", "diesel": "#34d399"},
}


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f).get("history", [])
    return []


def save_history(history: list):
    os.makedirs("docs", exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"history": history[-MAX_HISTORY:]}, f, indent=2)


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_html(data: dict, generated_at: str, history: list) -> str:
    cities  = data.get("cities", {})
    as_of   = data.get("as_of") or ""
    error   = data.get("error") or ""
    source  = data.get("source", "PPAC (MoPNG)")
    url     = data.get("url", "https://ppac.gov.in/consumer_info/retail_selling_price")

    def fmt(val):
        return "₹{:.2f}".format(val) if val is not None else "—"

    # --- City cards ---
    cards_html = ""
    for city in CITIES:
        cd = cities.get(city, {})
        petrol = cd.get("petrol")
        diesel = cd.get("diesel")
        flag   = {"Delhi": "🏛️", "Mumbai": "🌊", "Chennai": "🌴"}[city]
        col    = CITY_COLORS[city]
        cards_html += f"""
      <div class="card">
        <div class="card-header">
          <span class="card-icon">{flag}</span>
          <div><div class="card-label">{city}</div><div class="card-sub">Retail selling price</div></div>
        </div>
        <div class="fuel-row">
          <div class="fuel-item">
            <div class="fuel-tag" style="color:{col['petrol']}">⛽ Petrol</div>
            <div class="fuel-price" style="color:{col['petrol']}">{fmt(petrol)}<span class="fuel-unit">/L</span></div>
          </div>
          <div class="fuel-divider"></div>
          <div class="fuel-item">
            <div class="fuel-tag" style="color:{col['diesel']}">🚌 Diesel</div>
            <div class="fuel-price" style="color:{col['diesel']}">{fmt(diesel)}<span class="fuel-unit">/L</span></div>
          </div>
        </div>
        <div class="card-source">Source: <a href="{url}" target="_blank" rel="noopener">{source}</a></div>
      </div>"""

    # --- Error banner ---
    error_html = f'<div class="error-bar">{error}</div>' if error else ""

    # --- as_of line ---
    asof_html = f'<span>Effective from: <strong>{as_of}</strong></span><span class="sep">·</span>' if as_of else ""

    # --- Chart section ---
    history_json = json.dumps(history)
    if len(history) >= 2:
        # Build datasets for petrol prices of all 3 cities
        datasets_js = ""
        for city in CITIES:
            pc = CITY_COLORS[city]["petrol"]
            datasets_js += f"""
          {{
            label: "{city} Petrol",
            data: HISTORY.map(d => d["{city}"] && d["{city}"]["petrol"]),
            borderColor: "{pc}",
            backgroundColor: "{pc}18",
            tension: 0.35,
            fill: false,
            pointRadius: HISTORY.length > 20 ? 2 : 4,
            pointHoverRadius: 6,
          }},"""

        chart_section = f"""
  <section class="chart-section">
    <div class="chart-header">
      <h2 class="chart-title">Petrol Price Trend <span class="chart-sub">(daily, 07:00 IST)</span></h2>
    </div>
    <div class="chart-wrap">
      <canvas id="fuelChart"></canvas>
    </div>
  </section>"""

        chart_script = f"""
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const HISTORY = {history_json};
    const labels = HISTORY.map(d => d.ts_ist);

    Chart.defaults.color = "#8892a4";
    Chart.defaults.borderColor = "#2e3352";

    new Chart(document.getElementById("fuelChart"), {{
      type: "line",
      data: {{
        labels,
        datasets: [{datasets_js}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        interaction: {{ mode: "index", intersect: false }},
        scales: {{
          x: {{
            ticks: {{ color: "#8892a4", maxTicksLimit: 10, maxRotation: 30 }},
            grid: {{ color: "#2e335244" }}
          }},
          y: {{
            position: "left",
            ticks: {{
              color: "#8892a4",
              callback: v => "₹" + v.toFixed(2)
            }},
            grid: {{ color: "#2e335244" }},
            title: {{ display: true, text: "₹ / litre", color: "#8892a4", font: {{ size: 11 }} }}
          }}
        }},
        plugins: {{
          legend: {{
            labels: {{ color: "#e2e8f0", usePointStyle: true, padding: 20 }}
          }},
          tooltip: {{
            backgroundColor: "#1a1d27",
            borderColor: "#2e3352",
            borderWidth: 1,
            titleColor: "#e2e8f0",
            bodyColor: "#8892a4",
            padding: 12,
            callbacks: {{
              label: ctx => ctx.dataset.label + ": ₹" + ctx.parsed.y.toFixed(2) + "/L"
            }}
          }}
        }}
      }}
    }});
  </script>"""
    else:
        chart_section = """
  <section class="chart-section chart-empty">
    <h2 class="chart-title">Petrol Price Trend <span class="chart-sub">(daily)</span></h2>
    <p class="chart-empty-msg">Building history — check back tomorrow after the next update.</p>
  </section>"""
        chart_script = f"<script>const HISTORY = {history_json};</script>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>India Fuel Retail Prices</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
      --border: #2e3352; --accent: #f59e0b; --accent2: #3b82f6;
      --accent3: #10b981; --text: #e2e8f0; --text-muted: #8892a4;
      --red: #ef4444; --radius: 14px; --shadow: 0 4px 24px rgba(0,0,0,.45);
    }}
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }}
    a {{ color: var(--accent2); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 32px; }}
    .header-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .header-title {{ display: flex; align-items: center; gap: 14px; }}
    .flag {{ font-size: 2.2rem; }}
    h1 {{ font-size: 1.35rem; font-weight: 700; }}
    .subtitle {{ font-size: 0.82rem; color: var(--text-muted); margin-top: 2px; }}
    .header-right {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .update-badge {{ font-size: 0.78rem; color: var(--text-muted); background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 5px 12px; }}
    .nav-link {{ font-size: 0.78rem; color: var(--accent2); background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 5px 12px; }}
    main {{ max-width: 1100px; margin: 40px auto; padding: 0 24px 48px; }}
    .error-bar {{ background: #ef444418; border: 1px solid #ef444444; border-radius: 8px; padding: 10px 16px; font-size: 0.82rem; color: #f87171; margin-bottom: 20px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; margin-bottom: 24px; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px 26px 22px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 10px; min-height: 220px; justify-content: space-between; }}
    .card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }}
    .card-icon {{ font-size: 1.6rem; }}
    .card-label {{ font-size: 1rem; font-weight: 700; }}
    .card-sub {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 1px; }}
    .fuel-row {{ display: flex; align-items: center; gap: 0; flex: 1; }}
    .fuel-item {{ flex: 1; display: flex; flex-direction: column; gap: 4px; }}
    .fuel-item:last-child {{ text-align: right; }}
    .fuel-divider {{ width: 1px; background: var(--border); align-self: stretch; margin: 0 16px; }}
    .fuel-tag {{ font-size: 0.78rem; font-weight: 600; letter-spacing: .3px; }}
    .fuel-price {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -.5px; line-height: 1.1; }}
    .fuel-unit {{ font-size: 0.85rem; font-weight: 500; opacity: .75; margin-left: 2px; }}
    .card-source {{ font-size: 0.74rem; color: var(--text-muted); }}
    .info-bar {{ font-size: 0.78rem; color: var(--text-muted); text-align: center; padding: 12px 0 36px; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6px; }}
    .sep {{ opacity: .4; }}
    /* Chart */
    .chart-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px 24px 24px; box-shadow: var(--shadow); margin-bottom: 32px; }}
    .chart-header {{ margin-bottom: 20px; }}
    .chart-title {{ font-size: 1rem; font-weight: 700; color: var(--text); }}
    .chart-sub {{ font-size: 0.78rem; font-weight: 400; color: var(--text-muted); margin-left: 6px; }}
    .chart-wrap {{ position: relative; height: 300px; }}
    .chart-empty {{ text-align: center; padding: 40px 24px; }}
    .chart-empty-msg {{ color: var(--text-muted); font-size: 0.88rem; margin-top: 12px; }}
    @media (max-width: 600px) {{ header {{ padding: 14px 16px; }} main {{ padding: 0 14px 32px; margin-top: 24px; }} .fuel-price {{ font-size: 1.5rem; }} .chart-wrap {{ height: 220px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="header-title">
        <span class="flag">⛽</span>
        <div>
          <h1>India Fuel Retail Prices</h1>
          <p class="subtitle">Petrol &amp; Diesel — Delhi · Mumbai · Pune</p>
        </div>
      </div>
      <div class="header-right">
        <a class="nav-link" href="index.html">🛢️ Crude Oil Dashboard</a>
        <div class="update-badge">Updated: {generated_at} IST</div>
      </div>
    </div>
  </header>

  <main>
    {error_html}
    <div class="cards">
      {cards_html}
    </div>

    <div class="info-bar">
      {asof_html}
      <span>Updated: {generated_at} IST</span>
      <span class="sep">·</span>
      <span>Auto-updates daily at 07:00 IST via GitHub Actions</span>
      <span class="sep">·</span>
      <span>Source: <a href="{url}" target="_blank" rel="noopener">PPAC (MoPNG)</a></span>
    </div>

    {chart_section}

  </main>
{chart_script}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching fuel retail prices...")
    data = get_fuel_prices()
    cities = data.get("cities", {})

    print("Data:", json.dumps({
        city: vals for city, vals in cities.items()
    }, indent=2))

    if data.get("error"):
        print("Warning:", data["error"])

    ist_offset   = timedelta(hours=5, minutes=30)
    now_utc      = datetime.now(timezone.utc)
    now_ist      = now_utc + ist_offset
    generated_at = now_ist.strftime("%d %b %Y, %I:%M %p")
    ts_ist_short = now_ist.strftime("%d %b")   # Just date for daily x-axis labels

    # Load existing history, append today's data point if prices were fetched
    history = load_history()
    if cities:
        entry = {
            "ts_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ts_ist": ts_ist_short,
        }
        for city in CITIES:
            entry[city] = cities.get(city)
        history.append(entry)
        save_history(history)
        print(f"History: {len(history)} data point(s) saved to {HISTORY_FILE}")
    else:
        print("Skipping history append — no city prices fetched")

    os.makedirs("docs", exist_ok=True)
    html = build_html(data, generated_at, history)
    with open("docs/fuel.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated docs/fuel.html at {generated_at} IST")


if __name__ == "__main__":
    main()
