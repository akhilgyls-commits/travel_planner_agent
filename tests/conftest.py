"""
Shared pytest fixtures.

Sets required environment variables *before* any `app.*` module is
imported, since `app.config.get_settings()` is cached and reads env
vars at first call.
"""
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("USE_MOCK_APIS", "true")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c
