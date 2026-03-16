"""LLM provider factory."""

from __future__ import annotations

from docflow.config import Settings
from docflow.llm.base import DocumentClassification, LLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the configured LLM provider."""
    provider = settings.llm_provider

    if provider == "anthropic":
        from docflow.llm.anthropic import AnthropicProvider

        return AnthropicProvider(api_key=settings.anthropic_api_key)

    elif provider == "ollama":
        from docflow.llm.ollama import OllamaProvider

        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    elif provider == "openrouter":
        from docflow.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}")


__all__ = ["DocumentClassification", "LLMProvider", "get_llm_provider"]
