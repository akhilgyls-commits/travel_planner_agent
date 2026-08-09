"""
Aggregates all agent tools into a single list for easy import into
the LangGraph agent definition.
"""
from app.tools.cost_estimator_tool import estimate_trip_cost
from app.tools.maps_tool import get_local_transport_options, get_travel_distance
from app.tools.places_tool import search_attractions, search_hotels, search_restaurants
from app.tools.weather_tool import get_weather_forecast

ALL_TOOLS = [
    get_weather_forecast,
    get_travel_distance,
    get_local_transport_options,
    search_attractions,
    search_restaurants,
    search_hotels,
    estimate_trip_cost,
]

__all__ = ["ALL_TOOLS"]
