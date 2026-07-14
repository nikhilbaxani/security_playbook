"""Proveedor opcional: OpenAI."""

import os

from .base import LLMProvider, ProviderError

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderError("Falta OPENAI_API_KEY en el entorno o en .env.")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "SDK de OpenAI no instalado. Ejecuta: pip install openai"
            ) from exc
        self._client = OpenAI(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content
        if not text:
            raise ProviderError(f"OpenAI devolvió una respuesta vacía (modelo: {self.model}).")
        return text
