"""Proveedor opcional: Ollama (LLM local, sin API key ni costo)."""

import json
import os
import urllib.error
import urllib.request

from .base import LLMProvider, ProviderError

DEFAULT_MODEL = "llama3.1"
DEFAULT_HOST = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Usa la API HTTP de Ollama directamente — sin dependencias extra."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.host = (host or os.getenv("OLLAMA_HOST", DEFAULT_HOST)).rstrip("/")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as raw:
                body = json.loads(raw.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"No se pudo conectar con Ollama en {self.host}. "
                "¿Está corriendo? (ollama serve)"
            ) from exc
        text = body.get("message", {}).get("content", "")
        if not text:
            raise ProviderError(f"Ollama devolvió una respuesta vacía (modelo: {self.model}).")
        return text
