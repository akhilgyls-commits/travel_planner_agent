import time

import pytest

from app.services.session_service import SessionNotFoundError, SessionService


def test_create_and_get_session():
    svc = SessionService()
    session_id = svc.create_session("Kyoto, Japan")
    meta = svc.get(session_id)
    assert meta.session_id == session_id
    assert meta.destination == "Kyoto, Japan"


def test_get_nonexistent_session_raises():
    svc = SessionService()
    with pytest.raises(SessionNotFoundError):
        svc.get("does-not-exist")


def test_exists_false_for_unknown_session():
    svc = SessionService()
    assert svc.exists("nope") is False


def test_delete_session_removes_it():
    svc = SessionService()
    session_id = svc.create_session("Rome, Italy")
    assert svc.exists(session_id) is True
    svc.delete(session_id)
    assert svc.exists(session_id) is False


def test_touch_updates_last_active(monkeypatch):
    svc = SessionService()
    session_id = svc.create_session("Lisbon, Portugal")
    original = svc.get(session_id).last_active_at
    time.sleep(0.01)
    svc.touch(session_id)
    assert svc.get(session_id).last_active_at >= original


def test_register_existing_does_not_overwrite():
    svc = SessionService()
    session_id = svc.create_session("Paris, France")
    svc.register_existing(session_id, destination="Should Not Overwrite")
    assert svc.get(session_id).destination == "Paris, France"
