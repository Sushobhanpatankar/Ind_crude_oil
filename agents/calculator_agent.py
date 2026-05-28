"""
Agent 3 — INR per Barrel Calculator
Multiplies the USD/barrel crude price by the USD→INR exchange rate.
No network calls — pure computation.
"""

LITRES_PER_BARREL = 158.987


def calculate_inr_per_barrel(price_usd, rate_usd_inr) -> dict:
    """
    Calculate the cost of one barrel of Indian crude in INR.

    Args:
        price_usd: float — crude basket price in USD/barrel (from Agent 1)
        rate_usd_inr: float — INR per 1 USD (from Agent 2)

    Returns a dict with keys:
        price_usd, rate_usd_inr, price_inr, formula
    On missing input: price_inr=None, error (str)
    """
    if price_usd is None or rate_usd_inr is None:
        missing = []
        if price_usd is None:
            missing.append("crude price (USD/barrel)")
        if rate_usd_inr is None:
            missing.append("USD/INR exchange rate")
        return {
            "price_usd": price_usd,
            "rate_usd_inr": rate_usd_inr,
            "price_inr": None,
            "error": f"Missing upstream data: {', '.join(missing)}",
        }

    try:
        price_usd = float(price_usd)
        rate_usd_inr = float(rate_usd_inr)

        if price_usd <= 0 or rate_usd_inr <= 0:
            return {
                "price_usd": price_usd,
                "rate_usd_inr": rate_usd_inr,
                "price_inr": None,
                "error": "Price and rate must be positive values",
            }

        price_inr = round(price_usd * rate_usd_inr, 2)
        price_inr_per_litre = round(price_inr / LITRES_PER_BARREL, 4)

        return {
            "price_usd": price_usd,
            "rate_usd_inr": rate_usd_inr,
            "price_inr": price_inr,
            "price_inr_per_litre": price_inr_per_litre,
            "formula": f"{price_usd:.2f} USD/bbl × {rate_usd_inr:.4f} INR/USD = ₹{price_inr:,.2f}/bbl",
            "litre_formula": f"{price_inr:,.2f} INR / {LITRES_PER_BARREL} L = INR {price_inr_per_litre:.4f}/L",
        }

    except (TypeError, ValueError) as e:
        return {
            "price_usd": price_usd,
            "rate_usd_inr": rate_usd_inr,
            "price_inr": None,
            "error": f"Calculation error: {str(e)}",
        }


if __name__ == "__main__":
    import json
    # Quick smoke test
    result = calculate_inr_per_barrel(85.32, 95.79)
    print(json.dumps(result, indent=2))
