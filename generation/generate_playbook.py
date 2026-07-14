"""Arma el prompt final (system + few-shot + input del usuario) y llama al provider activo."""

import re
from datetime import datetime
from pathlib import Path

from providers import LLMProvider, get_provider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR = PROJECT_ROOT / "output"

INCIDENT_TYPES = [
    "ransomware",
    "credential leak",
    "ddos",
    "phishing exitoso",
    "insider threat",
    "malware genérico",
    "web defacement",
    "compromiso de cuenta cloud",
]


def load_system_prompt() -> str:
    system = (PROMPTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    few_shot = (PROMPTS_DIR / "few_shot_examples.md").read_text(encoding="utf-8")
    return f"{system}\n\n---\n\n{few_shot}"


RAG_RULES = """
# Referencias recuperadas (grounding)

A continuación tienes acciones y controles REALES recuperados de fuentes públicas
(RE&CT, NIST SP 800-53, NIST SP 800-61). Reglas adicionales obligatorias:

1. Cuando un paso del playbook se corresponda con una de estas referencias, cítala
   entre corchetes al final del paso, ej. [RA2301] o [IR-4] o [800-61 p.35].
2. NO cites IDs que no aparezcan en la lista de abajo — cada cita debe ser verificable.
3. Prioriza pasos respaldados por referencias; si añades un paso sin respaldo porque el
   contexto lo exige, no le pongas cita (déjalo sin corchetes, es honesto y verificable).
4. Añade al final del playbook una sección "## Fuentes citadas" listando cada ID usado
   con su fuente.
"""


def build_user_prompt(
    incident_type: str, context: str | None = None, references: str | None = None
) -> str:
    lines = [
        "Genera un playbook de respuesta a incidentes con la estructura obligatoria.",
        f"- Tipo de incidente: {incident_type}",
    ]
    if context and context.strip():
        lines.append(f"- Contexto de la organización: {context.strip()}")
    else:
        lines.append(
            "- Contexto de la organización: no proporcionado — declara los supuestos "
            "mínimos (tamaño de org, on-prem/cloud, backups) en 'Supuestos tomados'."
        )
    if references:
        lines.append(f"\n{RAG_RULES}\n{references}")
    return "\n".join(lines)


def retrieve_references(incident_type: str, context: str | None = None, top_k: int = 12) -> str:
    from retrieval.search import Retriever, format_references

    query = incident_type if not context else f"{incident_type}. {context}"
    return format_references(Retriever().search(query, top_k=top_k))


def generate_playbook(
    incident_type: str,
    context: str | None = None,
    provider: LLMProvider | None = None,
    use_rag: bool = False,
) -> str:
    provider = provider or get_provider()
    references = retrieve_references(incident_type, context) if use_rag else None
    return provider.generate(
        load_system_prompt(), build_user_prompt(incident_type, context, references)
    )


def save_playbook(markdown: str, incident_type: str, output_dir: Path | None = None) -> Path:
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", incident_type.lower()).strip("-") or "incidente"
    path = output_dir / f"playbook-{slug}-{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
