"""
Weather lookup tool.

Wraps OpenWeatherMap's forecast API. Falls back to deterministic mock
data when `USE_MOCK_APIS=true` or no API key is configured, so the
agent remains fully demoable without external credentials.
"""
import hashlib
import random
from datetime import date, timedelta
from typing import Any, Dict

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_MOCK_CONDITIONS = [
    "Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Clear Skies", "Windy",
]


def _seeded_random(seed_text: str) -> random.Random:
    """Deterministic RNG per (destination, date) so mock data is stable."""
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _mock_forecast(destination: str, start_date: str, days: int) -> Dict[str, Any]:
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        start = date.today()

    daily = []
    for i in range(min(days, 14)):
        d = start + timedelta(days=i)
        rng = _seeded_random(f"{destination.lower()}-{d.isoformat()}")
        daily.append(
            {
                "date": d.isoformat(),
                "condition": rng.choice(_MOCK_CONDITIONS),
                "temp_high_c": round(rng.uniform(15, 32), 1),
                "temp_low_c": round(rng.uniform(5, 18), 1),
                "precipitation_chance_pct": rng.randint(0, 70),
            }
        )
    return {
        "source": "mock",
        "destination": destination,
        "forecast": daily,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
def _fetch_real_forecast(destination: str, api_key: str) -> Dict[str, Any]:
    geo_url = "https://api.openweathermap.org/geo/1.0/direct"
    with httpx.Client(timeout=10) as client:
        geo_resp = client.get(
            geo_url, params={"q": destination, "limit": 1, "appid": api_key}
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise ValueError(f"Could not geocode destination: {destination}")
        lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        resp = client.get(
            forecast_url,
            params={
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "metric",
            },
        )
        resp.raise_for_status()
        return {"source": "openweathermap", "raw": resp.json()}


@tool("get_weather_forecast")
def get_weather_forecast(destination: str, start_date: str, num_days: int = 7) -> Dict[str, Any]:
    """
    Get the weather forecast for a travel destination.

    Args:
        destination: City and/or country, e.g. "Kyoto, Japan".
        start_date: ISO date (YYYY-MM-DD) of the trip start.
        num_days: Number of days to forecast (max 14).

    Returns:
        A dict with daily conditions, high/low temps (Celsius) and
        precipitation chance, useful for packing and itinerary advice.
    """
    settings = get_settings()
    if settings.use_mock_apis or not settings.openweather_api_key:
        logger.info("weather_tool.mock", extra={"destination": destination})
        return _mock_forecast(destination, start_date, num_days)

    try:
        logger.info("weather_tool.real_api", extra={"destination": destination})
        return _fetch_real_forecast(destination, settings.openweather_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "weather_tool.fallback_to_mock", extra={"error": str(exc)}
        )
        result = _mock_forecast(destination, start_date, num_days)
        result["note"] = "Live weather API unavailable; showing estimated data."
        return result
