"""Interfaz común que todo proveedor de LLM debe implementar."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Contrato mínimo: recibir un prompt de sistema + prompt de usuario y devolver texto.

    Para añadir un proveedor nuevo basta con crear una subclase que implemente
    `generate()` y registrarla en `providers/__init__.py`. El resto del código
    (prompts, generación, CLI) no necesita cambios.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Genera la respuesta del LLM como texto plano (Markdown)."""
        raise NotImplementedError


class ProviderError(RuntimeError):
    """Error de configuración o de llamada a un proveedor (API key ausente, SDK no instalado, etc.)."""
