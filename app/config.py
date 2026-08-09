"""
Centralized application configuration.

All environment-driven settings live here so the rest of the codebase
never touches `os.environ` directly. This makes behavior predictable,
testable (settings can be overridden/injected) and keeps secrets out
of source code.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "travel-planner-agent"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "*"

    # ---- LLM ----
    llm_provider: Literal["openai", "anthropic", "ollama"] = "ollama"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # ---- Tool APIs ----
    use_mock_apis: bool = True
    openweather_api_key: str = ""
    google_maps_api_key: str = ""
    google_places_api_key: str = ""

    # ---- Memory / sessions ----
    memory_max_messages: int = 20
    session_ttl_seconds: int = 3600

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_llm_credentials(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)

        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)

        if self.llm_provider == "ollama":
            return bool(self.ollama_model and self.ollama_base_url)

        return False


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton -- avoids re-parsing env on every call."""
    return Settings()
