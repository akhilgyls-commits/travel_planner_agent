import pytest

from app.agent.llm import LLMNotConfiguredError, build_chat_model
from app.agent.prompt_builder import build_planning_prompt
from app.config import Settings
from app.models.schemas import BudgetLevel, InterestEnum, TripPlanRequest


def _sample_request(**overrides):
    payload = dict(
        destination="Kyoto, Japan",
        start_date="2026-10-10",
        end_date="2026-10-17",
        travelers=2,
        budget_amount=3000,
        budget_currency="USD",
        budget_level=BudgetLevel.mid_range,
        interests=[InterestEnum.food, InterestEnum.history],
        origin_city="New York, USA",
    )
    payload.update(overrides)
    return TripPlanRequest(**payload)


def test_build_planning_prompt_includes_key_fields():
    req = _sample_request()
    prompt = build_planning_prompt(req)
    assert "Kyoto, Japan" in prompt
    assert "New York, USA" in prompt
    assert "2026-10-10" in prompt
    assert "2026-10-17" in prompt
    assert "food" in prompt
    assert "history" in prompt
    assert "2" in prompt  # travelers


def test_build_planning_prompt_handles_no_interests_or_origin():
    req = _sample_request(interests=[], origin_city=None)
    prompt = build_planning_prompt(req)
    assert "no specific preferences" in prompt
    assert "not specified" in prompt


def test_build_chat_model_raises_when_no_credentials():
    settings = Settings(
        llm_provider="openai",
        openai_api_key="",
        anthropic_api_key="",
        _env_file=None,
    )
    with pytest.raises(LLMNotConfiguredError):
        build_chat_model(settings)


def test_build_chat_model_succeeds_with_openai_key():
    settings = Settings(
        llm_provider="openai",
        openai_api_key="sk-fake-test-key",
        _env_file=None,
    )
    model = build_chat_model(settings)
    assert model is not None
