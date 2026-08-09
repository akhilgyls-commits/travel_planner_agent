"""
Places tool: attraction / restaurant / hotel search.

Wraps Google Places API when configured, otherwise generates
deterministic, interest-aware mock listings.
"""
import hashlib
import random
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_ATTRACTION_TEMPLATES = {
    "culture": ["{dest} Cultural Center", "Old Town {dest}", "{dest} Heritage Museum"],
    "history": ["{dest} Historical Fortress", "{dest} Ancient Quarter", "{dest} War Memorial"],
    "food": ["{dest} Night Food Market", "{dest} Culinary Walking Tour", "{dest} Central Market"],
    "nature": ["{dest} Botanical Gardens", "{dest} National Park Trailhead", "{dest} Riverside Park"],
    "adventure": ["{dest} Zipline Park", "{dest} Mountain Trail", "{dest} Rafting Base Camp"],
    "nightlife": ["{dest} Rooftop Bar District", "{dest} Live Music Quarter", "{dest} Night Market"],
    "relaxation": ["{dest} Hot Springs & Spa", "{dest} Public Gardens", "{dest} Lakeside Promenade"],
    "shopping": ["{dest} Main Shopping Street", "{dest} Artisan Market", "{dest} Design District"],
    "art": ["{dest} Museum of Modern Art", "{dest} Street Art District", "{dest} Contemporary Gallery"],
    "family": ["{dest} Family Aquarium", "{dest} Interactive Science Center", "{dest} City Zoo"],
    "beaches": ["{dest} Main Beach", "{dest} Hidden Cove Beach", "{dest} Beachfront Boardwalk"],
    "photography": ["{dest} Scenic Overlook", "{dest} Iconic Skyline Viewpoint", "{dest} Old Bridge"],
}

_DEFAULT_ATTRACTIONS = [
    "{dest} City Center", "{dest} Landmark Tower", "{dest} Main Square",
]

_CUISINE_STYLES = ["Local Traditional", "Modern Fusion", "Street Food", "Fine Dining", "Casual Cafe"]
_HOTEL_TIER_NAMES = {
    "budget": ["Cozy Inn", "Traveler's Hostel", "Budget Stay"],
    "mid_range": ["Comfort Suites", "City Center Hotel", "Boutique Hotel"],
    "luxury": ["Grand Palace Hotel", "Luxury Resort & Spa", "The Ritz Collection"],
}


def _rng(seed_text: str) -> random.Random:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _mock_attractions(destination: str, interests: Optional[List[str]], limit: int) -> List[Dict[str, Any]]:
    interests = interests or ["culture", "history", "food"]
    results = []
    rng = _rng(f"attractions-{destination}")
    pool: List[str] = []
    for interest in interests:
        templates = _ATTRACTION_TEMPLATES.get(interest.lower(), _DEFAULT_ATTRACTIONS)
        pool.extend(templates)
    if not pool:
        pool = _DEFAULT_ATTRACTIONS

    rng.shuffle(pool)
    for i, template in enumerate(pool[:limit]):
        name = template.format(dest=destination.split(",")[0])
        results.append(
            {
                "name": name,
                "category": interests[i % len(interests)],
                "rating": round(rng.uniform(3.9, 4.9), 1),
                "estimated_visit_duration_hours": rng.choice([1, 1.5, 2, 3, 4]),
                "estimated_cost_usd": rng.choice([0, 5, 10, 15, 25, 40]),
            }
        )
    return results


def _mock_restaurants(destination: str, limit: int) -> List[Dict[str, Any]]:
    rng = _rng(f"restaurants-{destination}")
    results = []
    dest_short = destination.split(",")[0]
    for i in range(limit):
        style = rng.choice(_CUISINE_STYLES)
        results.append(
            {
                "name": f"{style} House {dest_short} #{i + 1}",
                "cuisine_style": style,
                "rating": round(rng.uniform(3.7, 4.9), 1),
                "price_level": rng.choice(["$", "$$", "$$$", "$$$$"]),
                "avg_cost_per_person_usd": rng.choice([8, 15, 25, 40, 70]),
            }
        )
    return results


def _mock_hotels(destination: str, budget_level: str, limit: int) -> List[Dict[str, Any]]:
    rng = _rng(f"hotels-{destination}-{budget_level}")
    names = _HOTEL_TIER_NAMES.get(budget_level, _HOTEL_TIER_NAMES["mid_range"])
    price_ranges = {
        "budget": (25, 70),
        "mid_range": (80, 200),
        "luxury": (250, 800),
    }
    lo, hi = price_ranges.get(budget_level, (80, 200))
    dest_short = destination.split(",")[0]
    results = []
    for i in range(limit):
        base_name = names[i % len(names)]
        results.append(
            {
                "name": f"{base_name} {dest_short}",
                "star_rating": {"budget": 3, "mid_range": 4, "luxury": 5}.get(budget_level, 4),
                "guest_rating": round(rng.uniform(3.8, 4.9), 1),
                "price_per_night_usd": rng.randint(lo, hi),
            }
        )
    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
def _fetch_real_places(query: str, api_key: str) -> Dict[str, Any]:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, params={"query": query, "key": api_key})
        resp.raise_for_status()
        return resp.json()


@tool("search_attractions")
def search_attractions(
    destination: str, interests: Optional[List[str]] = None, limit: int = 6
) -> List[Dict[str, Any]]:
    """
    Search for tourist attractions and activities in a destination,
    optionally filtered/prioritized by traveler interests.

    Args:
        destination: City and/or country, e.g. "Kyoto, Japan".
        interests: List of interest tags, e.g. ["history", "food", "art"].
        limit: Max number of attractions to return (default 6).

    Returns:
        List of attractions with name, category, rating, typical visit
        duration and estimated entry cost in USD.
    """
    settings = get_settings()
    if settings.use_mock_apis or not settings.google_places_api_key:
        logger.info("places_tool.mock_attractions", extra={"destination": destination})
        return _mock_attractions(destination, interests, limit)

    try:
        data = _fetch_real_places(f"top attractions in {destination}", settings.google_places_api_key)
        return data.get("results", [])[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("places_tool.fallback_to_mock", extra={"error": str(exc)})
        return _mock_attractions(destination, interests, limit)


@tool("search_restaurants")
def search_restaurants(destination: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Search for restaurants in a destination across a range of price
    levels and cuisine styles.

    Args:
        destination: City and/or country, e.g. "Kyoto, Japan".
        limit: Max number of restaurants to return (default 6).

    Returns:
        List of restaurants with name, cuisine style, rating, price
        level ($ to $$$$) and average cost per person in USD.
    """
    settings = get_settings()
    if settings.use_mock_apis or not settings.google_places_api_key:
        logger.info("places_tool.mock_restaurants", extra={"destination": destination})
        return _mock_restaurants(destination, limit)

    try:
        data = _fetch_real_places(f"best restaurants in {destination}", settings.google_places_api_key)
        return data.get("results", [])[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("places_tool.fallback_to_mock", extra={"error": str(exc)})
        return _mock_restaurants(destination, limit)


@tool("search_hotels")
def search_hotels(destination: str, budget_level: str = "mid_range", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for hotels in a destination matching a budget tier.

    Args:
        destination: City and/or country, e.g. "Kyoto, Japan".
        budget_level: One of "budget", "mid_range", "luxury".
        limit: Max number of hotels to return (default 5).

    Returns:
        List of hotels with name, star rating, guest rating, and
        price per night in USD.
    """
    settings = get_settings()
    if settings.use_mock_apis or not settings.google_places_api_key:
        logger.info("places_tool.mock_hotels", extra={"destination": destination})
        return _mock_hotels(destination, budget_level, limit)

    try:
        data = _fetch_real_places(f"{budget_level} hotels in {destination}", settings.google_places_api_key)
        return data.get("results", [])[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("places_tool.fallback_to_mock", extra={"error": str(exc)})
        return _mock_hotels(destination, budget_level, limit)
