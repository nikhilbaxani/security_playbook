"""Proveedor por defecto: Google Gemini (capa gratuita)."""

import os

from .base import LLMProvider, ProviderError

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ProviderError(
                "Falta GEMINI_API_KEY. Copia .env.example a .env y pon tu clave "
                "(https://aistudio.google.com/apikey)."
            )
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        try:
            from google import genai
        except ImportError as exc:
            raise ProviderError(
                "SDK de Gemini no instalado. Ejecuta: pip install google-genai"
            ) from exc
        self._client = genai.Client(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        if not response.text:
            raise ProviderError(f"Gemini devolvió una respuesta vacía (modelo: {self.model}).")
        return response.text
