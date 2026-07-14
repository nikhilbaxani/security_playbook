"""Registro y factoría de proveedores de LLM.

El proveedor activo se elige con la variable de entorno LLM_PROVIDER
(gemini | claude | openai | ollama). Los imports son perezosos para que
solo haga falta instalar el SDK del proveedor que realmente se usa.
"""

import os

from .base import LLMProvider, ProviderError


def _make_gemini() -> LLMProvider:
    from .gemini_provider import GeminiProvider

    return GeminiProvider()


def _make_claude() -> LLMProvider:
    from .claude_provider import ClaudeProvider

    return ClaudeProvider()


def _make_openai() -> LLMProvider:
    from .openai_provider import OpenAIProvider

    return OpenAIProvider()


def _make_ollama() -> LLMProvider:
    from .ollama_provider import OllamaProvider

    return OllamaProvider()


PROVIDERS = {
    "gemini": _make_gemini,
    "claude": _make_claude,
    "openai": _make_openai,
    "ollama": _make_ollama,
}


def get_provider(name: str | None = None) -> LLMProvider:
    """Devuelve una instancia del proveedor pedido (o del definido en LLM_PROVIDER)."""
    name = (name or os.getenv("LLM_PROVIDER", "gemini")).strip().lower()
    factory = PROVIDERS.get(name)
    if factory is None:
        raise ProviderError(
            f"Proveedor desconocido: '{name}'. Opciones: {', '.join(sorted(PROVIDERS))}."
        )
    return factory()


__all__ = ["LLMProvider", "ProviderError", "PROVIDERS", "get_provider"]
