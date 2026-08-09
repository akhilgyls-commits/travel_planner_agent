"""
Trip cost estimation tool.

Pure computation tool (no external API) that rolls up a rough total
trip cost from component costs, so the LLM doesn't have to do
arithmetic itself (which is error prone).
"""
from typing import Any, Dict, Optional

from langchain_core.tools import tool

from app.logging_config import get_logger

logger = get_logger(__name__)

_DAILY_FOOD_ESTIMATE_USD = {"budget": 20, "mid_range": 45, "luxury": 100}
_DAILY_MISC_ESTIMATE_USD = {"budget": 10, "mid_range": 25, "luxury": 60}


@tool("estimate_trip_cost")
def estimate_trip_cost(
    num_days: int,
    travelers: int,
    hotel_price_per_night_usd: float,
    budget_level: str = "mid_range",
    flight_cost_per_person_usd: Optional[float] = None,
    local_transport_daily_usd: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Estimate total trip cost broken down by category (USD).

    Args:
        num_days: Number of days of the trip.
        travelers: Number of travelers.
        hotel_price_per_night_usd: Chosen/average hotel price per night.
        budget_level: One of "budget", "mid_range", "luxury" -- used to
            estimate food and miscellaneous daily spend per person.
        flight_cost_per_person_usd: Optional known/estimated flight cost
            per traveler. If omitted, it is excluded from the total.
        local_transport_daily_usd: Optional daily local transport
            spend per traveler. Defaults to a small heuristic if omitted.

    Returns:
        Dict with a cost breakdown (lodging, food, local_transport,
        flights, misc) and a grand total in USD.
    """
    budget_level = budget_level if budget_level in _DAILY_FOOD_ESTIMATE_USD else "mid_range"

    lodging_total = hotel_price_per_night_usd * num_days
    food_total = _DAILY_FOOD_ESTIMATE_USD[budget_level] * num_days * travelers
    misc_total = _DAILY_MISC_ESTIMATE_USD[budget_level] * num_days * travelers

    if local_transport_daily_usd is None:
        local_transport_daily_usd = {"budget": 5, "mid_range": 12, "luxury": 30}[budget_level]
    local_transport_total = local_transport_daily_usd * num_days * travelers

    flights_total = 0.0
    if flight_cost_per_person_usd is not None:
        flights_total = flight_cost_per_person_usd * travelers

    grand_total = lodging_total + food_total + misc_total + local_transport_total + flights_total

    result = {
        "currency": "USD",
        "breakdown": {
            "lodging": round(lodging_total, 2),
            "food": round(food_total, 2),
            "local_transport": round(local_transport_total, 2),
            "flights": round(flights_total, 2),
            "miscellaneous": round(misc_total, 2),
        },
        "grand_total": round(grand_total, 2),
        "per_traveler_total": round(grand_total / travelers, 2) if travelers else grand_total,
        "per_day_total": round(grand_total / num_days, 2) if num_days else grand_total,
    }
    logger.info("cost_estimator.computed", extra={"grand_total": result["grand_total"]})
    return result
