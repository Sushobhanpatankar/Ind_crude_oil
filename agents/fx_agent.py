"""
Agent 2 — USD to INR Exchange Rate
Primary source: RBI homepage FBIL reference rate widget (rbi.org.in)
Fallback: RBI Reference Rate Archive page
"""

import re
import requests

RBI_HOME_URL = "https://www.rbi.org.in/"
RBI_ARCHIVE_URL = "https://www.rbi.org.in/Scripts/ReferenceRateArchive.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

# Sanity bounds for USD/INR rate
RATE_MIN = 60.0
RATE_MAX = 150.0


def _parse_rate_from_homepage(html: str):
    """
    Parse USD/INR rate from RBI homepage Current Rates widget.
    The widget contains <dt>INR / 1 USD</dt><dd>: 95.7883</dd> pairs.
    Returns (rate: float, as_of: str) or (None, None).
    """
    try:
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: dt/dd definition list
        for dt in soup.find_all("dt"):
            text = dt.get_text(strip=True)
            if "USD" in text:
                dd = dt.find_next_sibling("dd")
                if dd:
                    raw = dd.get_text(strip=True)
                    # strip leading colon/space e.g. ": 95.7883"
                    raw = raw.lstrip(":").strip()
                    rate = float(raw)
                    if RATE_MIN <= rate <= RATE_MAX:
                        # Try to find the as_of date nearby
                        as_of = _extract_as_of(soup)
                        return rate, as_of

        # Strategy 2: regex fallback on raw HTML
        pattern = r'(?:INR\s*/\s*1\s*USD|USD)[^\d]*?([\d]{2,3}\.[\d]{2,6})'
        match = re.search(pattern, html)
        if match:
            rate = float(match.group(1))
            if RATE_MIN <= rate <= RATE_MAX:
                as_of = _extract_as_of(soup)
                return rate, as_of

    except Exception:
        pass
    return None, None


def _extract_as_of(soup) -> str:
    """Try to extract the date the rate is effective from the page."""
    try:
        # Look for text near "FBIL" or "Reference Rate"
        for tag in soup.find_all(string=re.compile(r'\d{2}[-/]\w{3}[-/]\d{4}|\d{2}/\d{2}/\d{4}')):
            text = tag.strip()
            if text:
                return text
    except Exception:
        pass
    return ""


def _fetch_from_archive() -> tuple:
    """
    Fallback: scrape the RBI Reference Rate Archive for today's USD/INR rate.
    Returns (rate: float, as_of: str) or (None, None).
    """
    try:
        from bs4 import BeautifulSoup
        from datetime import date

        # First GET to get ASP.NET form state
        resp = requests.get(RBI_ARCHIVE_URL, headers=HEADERS, timeout=(10, 30))
        resp.raise_for_status()
        try:
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            soup = BeautifulSoup(resp.text, "html.parser")

        viewstate = soup.find("input", {"id": "__VIEWSTATE"})
        eventval = soup.find("input", {"id": "__EVENTVALIDATION"})
        viewstategen = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})

        today = date.today()
        date_str = today.strftime("%d/%m/%Y")

        payload = {
            "__VIEWSTATE": viewstate["value"] if viewstate else "",
            "__EVENTVALIDATION": eventval["value"] if eventval else "",
            "__VIEWSTATEGENERATOR": viewstategen["value"] if viewstategen else "",
            "ctl00$ContentPlaceHolder1$txtDate": date_str,
            "ctl00$ContentPlaceHolder1$btnSearch": "Search",
        }

        resp2 = requests.post(RBI_ARCHIVE_URL, data=payload, headers={
            **HEADERS,
            "Referer": RBI_ARCHIVE_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        }, timeout=(10, 30))
        resp2.raise_for_status()

        try:
            soup2 = BeautifulSoup(resp2.text, "lxml")
        except Exception:
            soup2 = BeautifulSoup(resp2.text, "html.parser")

        # Table has columns: Date | USD | GBP | EUR | JPY (per 100)
        for row in soup2.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                # First cell is date, second is USD rate
                rate_text = cells[1].get_text(strip=True)
                try:
                    rate = float(rate_text)
                    if RATE_MIN <= rate <= RATE_MAX:
                        as_of = cells[0].get_text(strip=True)
                        return rate, as_of
                except ValueError:
                    continue

    except Exception:
        pass
    return None, None


def get_usd_inr_rate() -> dict:
    """
    Fetch the latest USD/INR reference rate from RBI (FBIL source).

    Returns a dict with keys:
      rate (float), source (str), as_of (str), url (str)
    On failure: rate=None, error (str)
    """
    try:
        resp = requests.get(RBI_HOME_URL, headers=HEADERS, timeout=(10, 30))
        resp.raise_for_status()
        rate, as_of = _parse_rate_from_homepage(resp.text)

        if rate is not None:
            return {
                "rate": rate,
                "as_of": as_of,
                "source": "RBI / FBIL",
                "url": RBI_HOME_URL,
            }

        # Primary parse failed — try archive
        rate, as_of = _fetch_from_archive()
        if rate is not None:
            return {
                "rate": rate,
                "as_of": as_of,
                "source": "RBI Reference Rate Archive",
                "url": RBI_ARCHIVE_URL,
            }

        return {
            "rate": None,
            "error": "Could not parse USD/INR rate from RBI homepage or archive",
            "source": "RBI",
            "url": RBI_HOME_URL,
        }

    except requests.RequestException as e:
        # Primary failed — try archive directly
        try:
            rate, as_of = _fetch_from_archive()
            if rate is not None:
                return {
                    "rate": rate,
                    "as_of": as_of,
                    "source": "RBI Reference Rate Archive",
                    "url": RBI_ARCHIVE_URL,
                }
        except Exception:
            pass

        return {
            "rate": None,
            "error": f"RBI request failed: {str(e)}",
            "source": "RBI",
            "url": RBI_HOME_URL,
        }
    except Exception as e:
        return {
            "rate": None,
            "error": f"Unexpected error in FX agent: {str(e)}",
            "source": "RBI",
            "url": RBI_HOME_URL,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(get_usd_inr_rate(), indent=2))
