from unittest.mock import MagicMock

import pytest


class FakeAgent:
    """Stand-in for TravelAgent that avoids real LLM/network calls."""

    def __init__(self):
        self.histories = {}

    def plan_trip(self, session_id, planning_prompt):
        self.histories.setdefault(session_id, []).append({"role": "user", "content": planning_prompt})
        answer = "## Trip Overview\nA wonderful mock itinerary.\n"
        self.histories[session_id].append({"role": "assistant", "content": answer})
        return {"answer": answer, "tools_used": ["get_weather_forecast", "search_hotels"]}

    def ask_followup(self, session_id, question):
        self.histories.setdefault(session_id, []).append({"role": "user", "content": question})
        answer = "Sure -- here's more detail."
        self.histories[session_id].append({"role": "assistant", "content": answer})
        return {"answer": answer, "tools_used": []}

    def get_history(self, session_id):
        return self.histories.get(session_id, [])

    def session_exists(self, session_id):
        return session_id in self.histories


@pytest.fixture()
def fake_agent(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr("app.api.routes.get_travel_agent", lambda: agent)
    return agent


VALID_PAYLOAD = {
    "destination": "Kyoto, Japan",
    "start_date": "2026-10-10",
    "end_date": "2026-10-17",
    "travelers": 2,
    "budget_amount": 3000,
    "budget_currency": "USD",
    "budget_level": "mid_range",
    "interests": ["food", "history"],
    "origin_city": "New York, USA",
}


def test_plan_trip_success(client, fake_agent):
    resp = client.post("/api/v1/trip/plan", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["destination"] == "Kyoto, Japan"
    assert body["duration_days"] == 7
    assert "session_id" in body and body["session_id"]
    assert "get_weather_forecast" in body["tools_used"]


def test_plan_trip_invalid_payload_returns_422(client, fake_agent):
    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["end_date"] = "2026-10-01"  # before start_date
    resp = client.post("/api/v1/trip/plan", json=bad_payload)
    assert resp.status_code == 422


def test_followup_requires_existing_session(client, fake_agent):
    resp = client.post(
        "/api/v1/trip/followup", json={"session_id": "unknown-session", "question": "What about food?"}
    )
    assert resp.status_code == 404


def test_followup_after_plan_succeeds(client, fake_agent):
    plan_resp = client.post("/api/v1/trip/plan", json=VALID_PAYLOAD)
    session_id = plan_resp.json()["session_id"]

    followup_resp = client.post(
        "/api/v1/trip/followup",
        json={"session_id": session_id, "question": "Can you suggest a vegetarian restaurant?"},
    )
    assert followup_resp.status_code == 200
    assert followup_resp.json()["session_id"] == session_id


def test_get_session_history(client, fake_agent):
    plan_resp = client.post("/api/v1/trip/plan", json=VALID_PAYLOAD)
    session_id = plan_resp.json()["session_id"]

    history_resp = client.get(f"/api/v1/trip/session/{session_id}")
    assert history_resp.status_code == 200
    messages = history_resp.json()["messages"]
    assert len(messages) >= 2


def test_get_history_for_unknown_session_returns_404(client, fake_agent):
    resp = client.get("/api/v1/trip/session/does-not-exist")
    assert resp.status_code == 404


def test_delete_session(client, fake_agent):
    plan_resp = client.post("/api/v1/trip/plan", json=VALID_PAYLOAD)
    session_id = plan_resp.json()["session_id"]

    del_resp = client.delete(f"/api/v1/trip/session/{session_id}")
    assert del_resp.status_code == 204

    del_again_resp = client.delete(f"/api/v1/trip/session/{session_id}")
    assert del_again_resp.status_code == 404
