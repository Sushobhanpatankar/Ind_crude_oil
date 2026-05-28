"""
Agents package — orchestrates all three sub-agents.
"""

from .crude_agent import get_crude_price
from .fx_agent import get_usd_inr_rate
from .calculator_agent import calculate_inr_per_barrel


def get_all_data() -> dict:
    """
    Run all three agents in sequence and return combined results.

    Returns:
        {
          "crude":  { price_usd, month, source, url, ... },
          "fx":     { rate, as_of, source, url, ... },
          "result": { price_usd, rate_usd_inr, price_inr, formula, ... },
        }
    """
    crude = get_crude_price()
    fx = get_usd_inr_rate()
    result = calculate_inr_per_barrel(
        crude.get("price_usd"),
        fx.get("rate"),
    )
    return {
        "crude": crude,
        "fx": fx,
        "result": result,
    }
