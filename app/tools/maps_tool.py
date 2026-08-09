"""
Maps tool: distance/duration estimates and local transportation options.

Wraps Google Maps Distance Matrix / Directions APIs when configured,
otherwise returns heuristic mock estimates.
"""
import hashlib
from typing import Any, Dict, List

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def _mock_distance(origin: str, destination: str) -> Dict[str, Any]:
    seed = int(hashlib.sha256(f"{origin}-{destination}".encode()).hexdigest(), 16)
    distance_km = 300 + (seed % 9000)  # 300 - 9300 km, deterministic
    # very rough heuristic: flight for >800km, else car/train
    if distance_km > 800:
        mode = "flight"
        duration_hours = round(distance_km / 750 + 1.5, 1)  # cruise speed + airport time
    else:
        mode = "train_or_car"
        duration_hours = round(distance_km / 90, 1)

    return {
        "source": "mock",
        "origin": origin,
        "destination": destination,
        "distance_km": distance_km,
        "recommended_mode": mode,
        "estimated_duration_hours": duration_hours,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
def _fetch_real_distance(origin: str, destination: str, api_key: str) -> Dict[str, Any]:
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            url,
            params={"origins": origin, "destinations": destination, "key": api_key},
        )
        resp.raise_for_status()
        return {"source": "google_maps", "raw": resp.json()}


@tool("get_travel_distance")
def get_travel_distance(origin: str, destination: str) -> Dict[str, Any]:
    """
    Estimate distance, travel time and recommended transportation mode
    between an origin city and a destination.

    Args:
        origin: Departure city, e.g. "New York, USA".
        destination: Arrival city, e.g. "Kyoto, Japan".

    Returns:
        Dict with distance_km, recommended_mode (flight/train_or_car),
        and estimated_duration_hours.
    """
    settings = get_settings()
    if settings.use_mock_apis or not settings.google_maps_api_key:
        logger.info("maps_tool.mock", extra={"origin": origin, "destination": destination})
        return _mock_distance(origin, destination)

    try:
        logger.info("maps_tool.real_api", extra={"origin": origin, "destination": destination})
        return _fetch_real_distance(origin, destination, settings.google_maps_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("maps_tool.fallback_to_mock", extra={"error": str(exc)})
        result = _mock_distance(origin, destination)
        result["note"] = "Live maps API unavailable; showing estimated data."
        return result


@tool("get_local_transport_options")
def get_local_transport_options(destination: str) -> List[Dict[str, str]]:
    """
    Get typical local transportation options available within a
    destination city (metro, buses, taxis, rideshare, bike rentals).

    Args:
        destination: City name, e.g. "Kyoto, Japan".

    Returns:
        A list of transport options with a name and short description.
    """
    logger.info("maps_tool.local_transport", extra={"destination": destination})
    # Static, general-purpose guidance -- always safe/deterministic,
    # since actual local-transit fine-detail varies too much to fake well.
    return [
        {
            "mode": "Public Transit (metro/bus)",
            "description": "Usually the cheapest and most efficient way to "
            f"get around {destination}; consider a multi-day transit pass.",
        },
        {
            "mode": "Taxi / Rideshare",
            "description": "Convenient for late nights, luggage, or "
            "when public transit doesn't cover an area.",
        },
        {
            "mode": "Walking",
            "description": "Great for compact city centers and historic districts.",
        },
        {
            "mode": "Bike Rental",
            "description": "A flexible, eco-friendly way to cover mid-range "
            "distances if the city has good bike infrastructure.",
        },
    ]
