"""
LLM client factory.

Keeps provider-selection logic (OpenAI vs Anthropic) in one place so
swapping providers is a config change, not a code change.
"""
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class LLMNotConfiguredError(RuntimeError):
    """Raised when the selected LLM provider has no API key configured."""


def build_chat_model(settings: Settings | None = None) -> BaseChatModel:
    settings = settings or get_settings()

    if not settings.has_llm_credentials:
        raise LLMNotConfiguredError(
            f"No API key configured for LLM provider '{settings.llm_provider}'. "
            "Set OPENAI_API_KEY or ANTHROPIC_API_KEY (and LLM_PROVIDER) in your "
            "environment."
        )

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        logger.info("llm.init", extra={"provider": "openai", "model": settings.openai_model})
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        logger.info("llm.init", extra={"provider": "anthropic", "model": settings.anthropic_model})
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
