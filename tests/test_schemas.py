import pytest
from pydantic import ValidationError

from app.models.schemas import TripPlanRequest


def _base_payload(**overrides):
    payload = dict(
        destination="Kyoto, Japan",
        start_date="2026-10-10",
        end_date="2026-10-17",
        travelers=2,
        budget_amount=3000,
        budget_currency="USD",
        budget_level="mid_range",
        interests=["food", "history"],
        origin_city="New York, USA",
    )
    payload.update(overrides)
    return payload


def test_valid_request_parses_and_computes_duration():
    req = TripPlanRequest(**_base_payload())
    assert req.duration_days == 7
    assert req.destination == "Kyoto, Japan"


def test_end_date_before_start_date_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(start_date="2026-10-17", end_date="2026-10-10"))


def test_end_date_equal_start_date_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(start_date="2026-10-10", end_date="2026-10-10"))


def test_trip_longer_than_60_days_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(start_date="2026-01-01", end_date="2026-04-01"))


def test_negative_budget_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(budget_amount=-100))


def test_zero_travelers_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(travelers=0))


def test_invalid_interest_rejected():
    with pytest.raises(ValidationError):
        TripPlanRequest(**_base_payload(interests=["skydiving_but_not_a_real_enum_value"]))


def test_destination_is_stripped():
    req = TripPlanRequest(**_base_payload(destination="  Kyoto, Japan  "))
    assert req.destination == "Kyoto, Japan"
