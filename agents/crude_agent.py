"""
Agent 1 — Indian Crude Basket Price
Source: PPAC (Petroleum Planning & Analysis Cell, MoPNG)
URL: https://ppac.gov.in/prices/international-prices-of-crude-oil

Notes:
  - Requires a browser-like session (cookies from initial page GET)
  - reportBy=4 is the USD/bbl option in the dropdown
  - Results are returned as a dict with string keys "1","2",...
  - Row "1" holds monthly averages; later rows are footnotes
"""

import re
import requests
from bs4 import BeautifulSoup

PPAC_PAGE_URL = "https://ppac.gov.in/prices/international-prices-of-crude-oil"
PPAC_AJAX_URL = "https://ppac.gov.in/AjaxController/getInternationalPricesCrudeOil"

# Months in Indian financial year order (April → March)
FY_MONTHS = [
    "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "january", "february", "march",
]

MONTH_DISPLAY = {
    "april": "April", "may": "May", "june": "June",
    "july": "July", "august": "August", "september": "September",
    "october": "October", "november": "November", "december": "December",
    "january": "January", "february": "February", "march": "March",
}

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_session():
    """Create a requests.Session with cookies obtained from the PPAC page."""
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    resp = session.get(PPAC_PAGE_URL, timeout=(10, 30))
    resp.raise_for_status()
    return session, resp.text


def _parse_page_meta(html: str):
    """
    From the PPAC prices page HTML, extract:
      - page_id (hidden input)
      - available financial year options from the dropdown
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    page_id_tag = soup.find("input", {"id": "page_id"})
    page_id = page_id_tag["value"] if page_id_tag else "30"

    fy_select = soup.find("select", {"id": "financialYear"})
    fy_options = []
    if fy_select:
        for opt in fy_select.find_all("option"):
            val = opt.get("value", "").strip()
            if val:
                fy_options.append(val)

    return page_id, fy_options


def _fetch_price_for_fy(session, fy: str, page_id: str):
    """
    POST to PPAC AJAX and return (price_float, month_key, today_price)
    for the given financial year.

    today_price is extracted from the footnote row if present
    (e.g. "Crude Oil Indian Basket as on 26.05.2026 is $ 102.05/bbl.")
    """
    headers = {
        "Referer": PPAC_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    payload = {
        "financialYear": fy,
        "reportBy": "4",   # 4 = $/bbl
        "pageId": page_id,
    }
    resp = session.post(PPAC_AJAX_URL, data=payload, headers=headers, timeout=(10, 30))
    resp.raise_for_status()
    data = resp.json()

    results = data.get("result", {})
    if not results:
        return None, None, None

    # Row "1" is the data row with monthly averages
    row = results.get("1")
    if not row:
        return None, None, None

    # Walk months in FY order, pick last non-empty value
    last_price = None
    last_month = None
    for m in FY_MONTHS:
        val = row.get(m)
        if val not in (None, "", 0, "0"):
            try:
                last_price = float(val)
                last_month = m
            except (TypeError, ValueError):
                pass

    # Try to extract today's spot price from footnote rows
    today_price = None
    for key in sorted(results.keys()):
        title = results[key].get("title", "")
        match = re.search(
            r'Indian Basket as on [\d.]+[\s\S]*?is\s*\$\s*([\d.]+)\s*/bbl',
            title, re.IGNORECASE
        )
        if match:
            try:
                today_price = float(match.group(1))
            except ValueError:
                pass

    return last_price, last_month, today_price


def _month_year_label(fy_month: str, fy_str: str) -> str:
    """Return a display string like 'May 2026' given a month key and FY string."""
    if not fy_month or not fy_str:
        return ""
    try:
        start_year = int(fy_str.split("-")[0])
        if fy_month in ("january", "february", "march"):
            year = start_year + 1
        else:
            year = start_year
        # PPAC FY labeling note: data for April 2026 comes back when
        # querying FY "2025-2026", so we derive year from actual month data
        # The returned title "2026-27" is the real FY; add 1 to start_year
        # for April-March months to get the correct calendar year
        # (April 2026 = FY 2026-27 → start_year "2025" in dropdown label)
        if fy_month not in ("january", "february", "march"):
            year = start_year + 1   # e.g. "2025-2026" → April 2026
        else:
            year = start_year + 1   # Jan-Mar are still in end year
        return f"{MONTH_DISPLAY[fy_month]} {year}"
    except Exception:
        return fy_month.capitalize()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_crude_price() -> dict:
    """
    Fetch the latest Indian Crude Basket price in USD/barrel from PPAC.

    Returns a dict:
      price_usd (float), month (str), today_price (float|None),
      source (str), url (str)
    On failure: price_usd=None, error (str)
    """
    try:
        session, html = _build_session()
        page_id, fy_options = _parse_page_meta(html)

        if not fy_options:
            return {
                "price_usd": None,
                "error": "No financial year options found on PPAC page",
                "source": "PPAC (MoPNG)",
                "url": PPAC_PAGE_URL,
            }

        # Try each available FY in order (most recent first)
        for fy in fy_options:
            price, month, today_price = _fetch_price_for_fy(session, fy, page_id)
            if price is not None:
                return {
                    "price_usd": price,
                    "month": _month_year_label(month, fy),
                    "month_key": month,
                    "today_price_usd": today_price,
                    "source": "PPAC (MoPNG)",
                    "url": PPAC_PAGE_URL,
                    "modified_date": "",
                }

        return {
            "price_usd": None,
            "error": f"PPAC returned no data for FY options: {fy_options}",
            "source": "PPAC (MoPNG)",
            "url": PPAC_PAGE_URL,
        }

    except requests.RequestException as e:
        return {
            "price_usd": None,
            "error": f"PPAC request failed: {str(e)}",
            "source": "PPAC (MoPNG)",
            "url": PPAC_PAGE_URL,
        }
    except Exception as e:
        return {
            "price_usd": None,
            "error": f"Unexpected error in crude agent: {str(e)}",
            "source": "PPAC (MoPNG)",
            "url": PPAC_PAGE_URL,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(get_crude_price(), indent=2))
