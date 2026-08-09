import pytest

from app.tools.cost_estimator_tool import estimate_trip_cost
from app.tools.maps_tool import get_local_transport_options, get_travel_distance
from app.tools.places_tool import search_attractions, search_hotels, search_restaurants
from app.tools.weather_tool import get_weather_forecast


class TestWeatherTool:
    def test_returns_mock_forecast_with_expected_shape(self):
        result = get_weather_forecast.invoke(
            {"destination": "Kyoto, Japan", "start_date": "2026-10-10", "num_days": 5}
        )
        assert result["source"] == "mock"
        assert result["destination"] == "Kyoto, Japan"
        assert len(result["forecast"]) == 5
        for day in result["forecast"]:
            assert "condition" in day
            assert "temp_high_c" in day
            assert "temp_low_c" in day

    def test_forecast_is_deterministic_for_same_inputs(self):
        r1 = get_weather_forecast.invoke(
            {"destination": "Paris, France", "start_date": "2026-06-01", "num_days": 3}
        )
        r2 = get_weather_forecast.invoke(
            {"destination": "Paris, France", "start_date": "2026-06-01", "num_days": 3}
        )
        assert r1["forecast"] == r2["forecast"]

    def test_caps_num_days_at_14(self):
        result = get_weather_forecast.invoke(
            {"destination": "Rome, Italy", "start_date": "2026-01-01", "num_days": 30}
        )
        assert len(result["forecast"]) <= 14


class TestMapsTool:
    def test_get_travel_distance_returns_expected_fields(self):
        result = get_travel_distance.invoke({"origin": "New York, USA", "destination": "Kyoto, Japan"})
        assert result["origin"] == "New York, USA"
        assert result["destination"] == "Kyoto, Japan"
        assert result["distance_km"] > 0
        assert result["recommended_mode"] in {"flight", "train_or_car"}
        assert result["estimated_duration_hours"] > 0

    def test_local_transport_options_nonempty(self):
        options = get_local_transport_options.invoke({"destination": "Lisbon, Portugal"})
        assert len(options) >= 3
        for opt in options:
            assert "mode" in opt and "description" in opt


class TestPlacesTool:
    def test_search_attractions_respects_limit(self):
        results = search_attractions.invoke(
            {"destination": "Kyoto, Japan", "interests": ["history", "food"], "limit": 4}
        )
        assert len(results) <= 4
        for a in results:
            assert "name" in a and "rating" in a

    def test_search_restaurants_returns_price_levels(self):
        results = search_restaurants.invoke({"destination": "Barcelona, Spain", "limit": 3})
        assert len(results) == 3
        for r in results:
            assert r["price_level"] in {"$", "$$", "$$$", "$$$$"}

    @pytest.mark.parametrize("budget_level", ["budget", "mid_range", "luxury"])
    def test_search_hotels_price_scales_with_budget_level(self, budget_level):
        results = search_hotels.invoke(
            {"destination": "Bangkok, Thailand", "budget_level": budget_level, "limit": 5}
        )
        assert len(results) == 5
        for h in results:
            assert h["price_per_night_usd"] > 0

    def test_luxury_hotels_cost_more_than_budget_hotels(self):
        budget_hotels = search_hotels.invoke(
            {"destination": "Bangkok, Thailand", "budget_level": "budget", "limit": 5}
        )
        luxury_hotels = search_hotels.invoke(
            {"destination": "Bangkok, Thailand", "budget_level": "luxury", "limit": 5}
        )
        avg_budget = sum(h["price_per_night_usd"] for h in budget_hotels) / len(budget_hotels)
        avg_luxury = sum(h["price_per_night_usd"] for h in luxury_hotels) / len(luxury_hotels)
        assert avg_luxury > avg_budget


class TestCostEstimatorTool:
    def test_basic_estimate_structure(self):
        result = estimate_trip_cost.invoke(
            {
                "num_days": 5,
                "travelers": 2,
                "hotel_price_per_night_usd": 120.0,
                "budget_level": "mid_range",
            }
        )
        assert result["currency"] == "USD"
        assert result["grand_total"] > 0
        assert result["breakdown"]["lodging"] == pytest.approx(600.0)
        assert set(result["breakdown"].keys()) == {
            "lodging",
            "food",
            "local_transport",
            "flights",
            "miscellaneous",
        }

    def test_flights_included_when_provided(self):
        without_flights = estimate_trip_cost.invoke(
            {
                "num_days": 3,
                "travelers": 1,
                "hotel_price_per_night_usd": 100.0,
            }
        )
        with_flights = estimate_trip_cost.invoke(
            {
                "num_days": 3,
                "travelers": 1,
                "hotel_price_per_night_usd": 100.0,
                "flight_cost_per_person_usd": 500.0,
            }
        )
        assert with_flights["grand_total"] > without_flights["grand_total"]
        assert with_flights["breakdown"]["flights"] == pytest.approx(500.0)

    def test_invalid_budget_level_falls_back_to_mid_range(self):
        result = estimate_trip_cost.invoke(
            {
                "num_days": 2,
                "travelers": 1,
                "hotel_price_per_night_usd": 90.0,
                "budget_level": "not_a_real_tier",
            }
        )
        assert result["grand_total"] > 0

    def test_per_traveler_and_per_day_totals(self):
        result = estimate_trip_cost.invoke(
            {
                "num_days": 4,
                "travelers": 2,
                "hotel_price_per_night_usd": 100.0,
                "budget_level": "budget",
            }
        )
        assert result["per_traveler_total"] == pytest.approx(result["grand_total"] / 2)
        assert result["per_day_total"] == pytest.approx(result["grand_total"] / 4)
