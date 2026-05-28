"""
Static site generator for GitHub Pages deployment.
Fetches live data from PPAC and RBI, then writes a self-contained index.html
into the docs/ directory. Run by the GitHub Actions workflow on a schedule.
"""

import json
import os
from datetime import datetime, timezone

from agents import get_all_data


def build_html(data: dict, generated_at: str) -> str:
    crude = data.get("crude", {})
    fx = data.get("fx", {})
    result = data.get("result", {})

    def fmt_inr(val):
        if val is None:
            return "Unavailable"
        return "₹{:,.2f}".format(val)

    def fmt_usd(val):
        if val is None:
            return "Unavailable"
        return "${:,.2f}".format(val)

    crude_price     = fmt_usd(crude.get("price_usd"))
    crude_month     = (crude.get("month") or "") + (" avg." if crude.get("price_usd") else "")
    crude_today     = fmt_usd(crude.get("today_price_usd")) if crude.get("today_price_usd") else None
    crude_error     = crude.get("error", "")

    fx_rate         = "₹{:.4f} / $1".format(fx["rate"]) if fx.get("rate") else "Unavailable"
    fx_asof         = fx.get("as_of", "")
    fx_error        = fx.get("error", "")

    inr_barrel      = fmt_inr(result.get("price_inr"))
    inr_litre       = fmt_inr(result.get("price_inr_per_litre"))
    formula         = result.get("formula", "")
    litre_formula   = result.get("litre_formula", "")
    result_error    = result.get("error", "")

    crude_today_html = (
        f'<div class="today-tag">Today\'s spot: <strong>{crude_today}</strong></div>'
        if crude_today else ""
    )
    crude_error_html  = f'<div class="card-error">{crude_error}</div>'  if crude_error  else ""
    fx_error_html     = f'<div class="card-error">{fx_error}</div>'     if fx_error     else ""
    result_error_html = f'<div class="card-error">{result_error}</div>' if result_error else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Indian Crude Oil Cost Dashboard</title>
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
    header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 32px; }}
    .header-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .header-title {{ display: flex; align-items: center; gap: 14px; }}
    .flag {{ font-size: 2.2rem; }}
    h1 {{ font-size: 1.35rem; font-weight: 700; }}
    .subtitle {{ font-size: 0.82rem; color: var(--text-muted); margin-top: 2px; }}
    .update-badge {{ font-size: 0.78rem; color: var(--text-muted); background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 5px 12px; }}
    main {{ max-width: 1100px; margin: 40px auto; padding: 0 24px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 24px; margin-bottom: 24px; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px 26px 22px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 6px; }}
    .card-result {{ border-color: #10b98144; background: linear-gradient(145deg, #1a1d27 0%, #0f1f1a 100%); }}
    .card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
    .card-icon {{ font-size: 1.6rem; }}
    .card-label {{ font-size: 0.9rem; font-weight: 600; }}
    .card-sub {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 1px; }}
    .agent-badge {{ margin-left: auto; font-size: 0.68rem; font-weight: 700; letter-spacing: .5px; text-transform: uppercase; color: var(--accent); background: #f59e0b18; border: 1px solid #f59e0b44; border-radius: 20px; padding: 3px 9px; white-space: nowrap; }}
    .agent-badge-result {{ color: var(--accent3); background: #10b98118; border-color: #10b98144; }}
    .card-value {{ font-size: 2rem; font-weight: 800; letter-spacing: -.5px; line-height: 1.1; margin: 4px 0 2px; }}
    .result-value {{ font-size: 2.4rem; color: var(--accent3); }}
    .card-detail {{ font-size: 0.8rem; color: var(--text-muted); }}
    .litre-line {{ font-size: 0.88rem; color: #a7f3d0; margin-top: 2px; }}
    .formula {{ font-family: "Cascadia Code", "Consolas", monospace; font-size: 0.76rem; color: #6b7aa0; background: var(--surface2); border-radius: 6px; padding: 6px 10px; margin-top: 4px; word-break: break-word; }}
    .card-source {{ margin-top: 6px; font-size: 0.74rem; color: var(--text-muted); }}
    .card-error {{ background: #ef444418; border: 1px solid #ef444444; border-radius: 6px; padding: 6px 10px; font-size: 0.76rem; color: #f87171; margin-top: 4px; }}
    .today-tag {{ font-size: 0.78rem; color: var(--accent); margin-top: 2px; }}
    .info-bar {{ font-size: 0.78rem; color: var(--text-muted); text-align: center; padding: 12px 0 32px; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6px; }}
    .sep {{ opacity: .4; }}
    @media (max-width: 600px) {{ header {{ padding: 14px 16px; }} main {{ padding: 0 14px; margin-top: 24px; }} .card-value {{ font-size: 1.6rem; }} .result-value {{ font-size: 2rem; }} }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="header-title">
        <span class="flag">🛢️</span>
        <div>
          <h1>Indian Crude Oil Cost Dashboard</h1>
          <p class="subtitle">Real-time cost of Indian crude in Indian Rupees — per barrel &amp; per litre</p>
        </div>
      </div>
      <div class="update-badge">Updated: {generated_at} IST</div>
    </div>
  </header>

  <main>
    <div class="cards">

      <div class="card">
        <div class="card-header">
          <span class="card-icon">🛢️</span>
          <div><div class="card-label">Indian Crude Basket</div><div class="card-sub">USD per barrel</div></div>
          <span class="agent-badge">Agent 1</span>
        </div>
        <div class="card-value">{crude_price}</div>
        <div class="card-detail">{crude_month}</div>
        {crude_today_html}
        <div class="card-source">Source: <a href="https://ppac.gov.in/prices/international-prices-of-crude-oil" target="_blank" rel="noopener">PPAC (MoPNG)</a></div>
        {crude_error_html}
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-icon">💱</span>
          <div><div class="card-label">USD / INR Rate</div><div class="card-sub">INR per 1 US Dollar</div></div>
          <span class="agent-badge">Agent 2</span>
        </div>
        <div class="card-value">{fx_rate}</div>
        <div class="card-detail">{("As of: " + fx_asof) if fx_asof else ""}</div>
        <div class="card-source">Source: <a href="https://www.rbi.org.in/" target="_blank" rel="noopener">RBI / FBIL</a></div>
        {fx_error_html}
      </div>

      <div class="card card-result">
        <div class="card-header">
          <span class="card-icon">🇮🇳</span>
          <div><div class="card-label">Cost in INR</div><div class="card-sub">At Indian shores</div></div>
          <span class="agent-badge agent-badge-result">Agent 3</span>
        </div>
        <div class="card-value result-value">{inr_barrel} / bbl</div>
        <div class="litre-line">Per litre: <strong>{inr_litre} / L</strong></div>
        <div class="formula">{formula}</div>
        <div class="formula">{litre_formula}</div>
        {result_error_html}
      </div>

    </div>

    <div class="info-bar">
      <span>Data fetched: {generated_at} IST</span>
      <span class="sep">·</span>
      <span>Auto-updates every 6 hours via GitHub Actions</span>
      <span class="sep">·</span>
      <span>Sources: <a href="https://ppac.gov.in" target="_blank" rel="noopener">PPAC</a> &amp; <a href="https://rbi.org.in" target="_blank" rel="noopener">RBI</a></span>
    </div>
  </main>
</body>
</html>"""


def main():
    print("Fetching live data...")
    data = get_all_data()
    print("Data:", json.dumps({
        "crude_usd": data.get("crude", {}).get("price_usd"),
        "fx_rate": data.get("fx", {}).get("rate"),
        "price_inr": data.get("result", {}).get("price_inr"),
        "price_inr_per_litre": data.get("result", {}).get("price_inr_per_litre"),
    }, indent=2))

    now_ist = datetime.now(timezone.utc)
    # Convert UTC to IST (UTC+5:30)
    from datetime import timedelta
    ist_offset = timedelta(hours=5, minutes=30)
    now_ist = (datetime.now(timezone.utc) + ist_offset)
    generated_at = now_ist.strftime("%d %b %Y, %I:%M %p")

    html = build_html(data, generated_at)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated docs/index.html at {generated_at} IST")


if __name__ == "__main__":
    main()
