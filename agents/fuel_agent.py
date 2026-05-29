"""
Fuel Retail Price Agent
Source: PPAC Daily Metro Price PDF (Petroleum Planning & Analysis Cell, MoPNG)

The PPAC metro RSP page links to a daily PDF titled:
  PP_9_a_DailyPriceMSHSD_Metro_<date>.pdf
This PDF contains petrol and diesel prices for Delhi, Mumbai, Chennai, Kolkata
in reverse-chronological order (most recent row first).

Notes:
  - PPAC's page is JavaScript-rendered; tables are not in the HTML.
  - The daily PDF is embedded as a link in the page source.
  - PDF prices have a character-spacing quirk: "1 02.12" means 102.12.
  - pdfplumber is used for reliable text extraction.
"""

import io
import re
import requests
import pdfplumber

PPAC_METRO_PAGE = (
    "https://ppac.gov.in/"
    "retail-selling-price-rsp-of-petrol-diesel-and-domestic-lpg/"
    "rsp-of-petrol-and-diesel-in-metro-cities-since-16-6-2017"
)

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

CITIES = ["Delhi", "Mumbai", "Chennai"]

# Petrol column order in PDF: Delhi(0), Mumbai(1), Chennai(2), Kolkata(3)
# Diesel column order in PDF: Delhi(4), Mumbai(5), Chennai(6), Kolkata(7)
_CITY_IDX = {
    "Delhi":   {"petrol": 0, "diesel": 4},
    "Mumbai":  {"petrol": 1, "diesel": 5},
    "Chennai": {"petrol": 2, "diesel": 6},
    "Kolkata": {"petrol": 3, "diesel": 7},
}

# Price regex: handles both split prices ("1 02.12" → 102.12) and plain ("95.20")
_PRICE_RE = re.compile(r"(\d)\s+(\d{1,2}\.\d{2})|(\d{2,3}\.\d{2})")

# PDF URL pattern embedded in the page source
_PDF_URL_RE = re.compile(
    r"https://ppac\.gov\.in/uploads/page-images/\d+_PP_9_a_DailyPriceMSHSD_Metro_[\d.]+\.pdf"
)

# Data row starts with a date like "29-May-26 "
_DATA_ROW_RE = re.compile(r"^\d+-\w{3}-\d{2}\s")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DATE_PAT = re.compile(r"\d{1,2}-\w{3}-\d{2}")


def _extract_prices(line: str) -> list[float]:
    """
    Extract all price floats from a PDF text line.
    Split prices like '1 02.12' are rejoined → 102.12.
    Dates (e.g. '29-May-26') are removed first to prevent false matches
    where a trailing date digit (like '6') + space + price ('95.20')
    would be misread as 695.20.
    """
    clean = _DATE_PAT.sub("", line)
    prices = []
    for m in _PRICE_RE.finditer(clean):
        if m.group(1) is not None:
            prices.append(float(m.group(1) + m.group(2)))
        else:
            prices.append(float(m.group(3)))
    return prices


def _find_pdf_url(html: str) -> str | None:
    """Extract the daily metro price PDF URL from page HTML."""
    m = _PDF_URL_RE.search(html)
    return m.group(0) if m else None


def _parse_pdf(pdf_bytes: bytes) -> dict:
    """
    Parse the PPAC metro daily PDF.
    Returns city prices dict from the most-recent row (first data row).
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not _DATA_ROW_RE.match(line):
                    continue
                prices = _extract_prices(line)
                if len(prices) < 8:
                    continue   # malformed row
                cities = {}
                for city in CITIES:
                    pi = _CITY_IDX[city]["petrol"]
                    di = _CITY_IDX[city]["diesel"]
                    cities[city] = {
                        "petrol": prices[pi],
                        "diesel": prices[di],
                    }
                return cities   # first (most recent) row is sufficient
    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_fuel_prices() -> dict:
    """
    Fetch today's petrol & diesel retail prices for Delhi, Mumbai, Chennai.
    Data source: PPAC daily metro price PDF.

    Returns:
        {
            "as_of":  "29 May 2026",
            "cities": {
                "Delhi":   {"petrol": 102.12, "diesel": 95.20},
                "Mumbai":  {"petrol": 111.21, "diesel": 97.83},
                "Chennai": {"petrol": 107.77, "diesel": 99.55},
            },
            "source": "PPAC (MoPNG)",
            "url":    "https://...",
            "error":  None,
        }
    On failure: cities={}, error=<message>.
    """
    try:
        session = requests.Session()
        session.headers.update(BASE_HEADERS)

        # Step 1: fetch the PPAC metro RSP page to find today's PDF URL
        page_resp = session.get(PPAC_METRO_PAGE, timeout=(10, 30))
        page_resp.raise_for_status()

        pdf_url = _find_pdf_url(page_resp.text)
        if not pdf_url:
            return {
                "as_of":  None,
                "cities": {},
                "source": "PPAC (MoPNG)",
                "url":    PPAC_METRO_PAGE,
                "error":  "Daily metro price PDF link not found on PPAC page",
            }

        # Step 2: download the PDF
        pdf_resp = session.get(pdf_url, timeout=(10, 60))
        pdf_resp.raise_for_status()
        if b"%PDF" not in pdf_resp.content[:8]:
            return {
                "as_of":  None,
                "cities": {},
                "source": "PPAC (MoPNG)",
                "url":    pdf_url,
                "error":  "Downloaded file is not a valid PDF",
            }

        # Step 3: parse prices from PDF
        cities = _parse_pdf(pdf_resp.content)
        if not cities:
            return {
                "as_of":  None,
                "cities": {},
                "source": "PPAC (MoPNG)",
                "url":    pdf_url,
                "error":  "Could not parse price data from PDF",
            }

        # Extract date from PDF URL (e.g., "...Metro_29.05.2026.pdf")
        date_m = re.search(r"Metro_(\d{2}\.\d{2}\.\d{4})\.pdf", pdf_url)
        as_of = date_m.group(1) if date_m else None

        return {
            "as_of":  as_of,
            "cities": cities,
            "source": "PPAC (MoPNG)",
            "url":    pdf_url,
            "error":  None,
        }

    except requests.RequestException as e:
        return {
            "as_of":  None,
            "cities": {},
            "source": "PPAC (MoPNG)",
            "url":    PPAC_METRO_PAGE,
            "error":  f"Request failed: {e}",
        }
    except Exception as e:
        return {
            "as_of":  None,
            "cities": {},
            "source": "PPAC (MoPNG)",
            "url":    PPAC_METRO_PAGE,
            "error":  f"Unexpected error: {e}",
        }


if __name__ == "__main__":
    import json
    print(json.dumps(get_fuel_prices(), indent=2))
