"""Proveedor opcional: Anthropic Claude."""

import os

from .base import LLMProvider, ProviderError

DEFAULT_MODEL = "claude-sonnet-5"


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderError("Falta ANTHROPIC_API_KEY en el entorno o en .env.")
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(
                "SDK de Anthropic no instalado. Ejecuta: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = [block.text for block in response.content if block.type == "text"]
        if not parts:
            raise ProviderError(f"Claude devolvió una respuesta vacía (modelo: {self.model}).")
        return "".join(parts)
