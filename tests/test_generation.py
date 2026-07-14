"""Tests del núcleo: prompts, factoría de proveedores y guardado. Sin llamadas a APIs reales."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generation.generate_playbook import (
    build_user_prompt,
    generate_playbook,
    load_system_prompt,
    save_playbook,
)
from providers import PROVIDERS, LLMProvider, ProviderError, get_provider


class FakeProvider(LLMProvider):
    """Provider de prueba: captura los prompts y devuelve un texto fijo."""

    def __init__(self):
        self.system_prompt = None
        self.user_prompt = None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return "# Playbook: test\n\ncontenido"


def test_system_prompt_incluye_estructura_nist():
    prompt = load_system_prompt()
    assert "NIST SP 800-61" in prompt
    assert "Supuestos tomados" in prompt
    # los few-shot deben ir concatenados
    assert "few-shot" in prompt.lower()


def test_user_prompt_con_contexto():
    prompt = build_user_prompt("ransomware", "on-prem, sin backups")
    assert "ransomware" in prompt
    assert "on-prem, sin backups" in prompt


def test_user_prompt_sin_contexto_pide_supuestos():
    prompt = build_user_prompt("ddos", None)
    assert "Supuestos tomados" in prompt


def test_generate_playbook_usa_el_provider_inyectado():
    fake = FakeProvider()
    result = generate_playbook("credential leak", "M365, MFA parcial", provider=fake)
    assert result.startswith("# Playbook")
    assert "credential leak" in fake.user_prompt
    assert "NIST SP 800-61" in fake.system_prompt


def test_get_provider_rechaza_nombre_desconocido():
    with pytest.raises(ProviderError, match="Proveedor desconocido"):
        get_provider("inexistente")


def test_registro_incluye_los_cuatro_proveedores():
    assert set(PROVIDERS) == {"gemini", "claude", "openai", "ollama"}


def test_gemini_sin_api_key_da_error_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        get_provider()


def test_user_prompt_con_referencias_incluye_reglas_de_cita():
    refs = "### [RA2301] (RE&CT | etapa: containment)\nBlock domain on DNS server\n"
    prompt = build_user_prompt("ransomware", "on-prem", references=refs)
    assert "[RA2301]" in prompt
    assert "Fuentes citadas" in prompt
    assert "NO cites IDs que no aparezcan" in prompt


def test_react_to_chunks():
    from retrieval.ingest import react_to_chunks

    stix = {
        "objects": [
            {
                "type": "x-react-action",
                "name": "Block external IP address",
                "description": "Block an external IP address on the border firewall.",
                "kill_chain_phases": [{"phase_name": "containment"}],
                "external_references": [
                    {
                        "source_name": "atc-react",
                        "external_id": "RA2101",
                        "url": "https://example.org/RA2101",
                    }
                ],
            },
            {"type": "x-react-stage", "name": "Containment"},
            {"type": "x-react-action", "name": "Sin descripcion ni id"},
        ]
    }
    chunks = react_to_chunks(stix)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["ref_id"] == "RA2101"
    assert chunks[0]["metadata"]["stage"] == "containment"
    assert "Block an external IP" in chunks[0]["text"]


def test_oscal_to_chunks_filtra_familias_y_withdrawn():
    from retrieval.ingest import oscal_to_chunks

    catalog = {
        "catalog": {
            "groups": [
                {
                    "id": "ir",
                    "title": "Incident Response",
                    "controls": [
                        {
                            "id": "ir-4",
                            "title": "Incident Handling",
                            "props": [{"name": "label", "value": "IR-04"}],
                            "parts": [{"name": "statement", "prose": "Implement incident handling."}],
                            "controls": [
                                {
                                    "id": "ir-4.1",
                                    "title": "Automated Processes",
                                    "props": [{"name": "label", "value": "IR-04(01)"}],
                                    "parts": [{"name": "statement", "prose": "Automate handling."}],
                                },
                                {
                                    "id": "ir-4.2",
                                    "title": "Withdrawn one",
                                    "props": [{"name": "status", "value": "withdrawn"}],
                                    "parts": [{"name": "statement", "prose": "old"}],
                                },
                            ],
                        }
                    ],
                },
                {
                    "id": "ac",
                    "title": "Access Control",
                    "controls": [
                        {
                            "id": "ac-1",
                            "title": "Policy",
                            "parts": [{"name": "statement", "prose": "irrelevante aqui"}],
                        }
                    ],
                },
            ]
        }
    }
    chunks = oscal_to_chunks(catalog)
    ids = [c["metadata"]["ref_id"] for c in chunks]
    assert ids == ["IR-04", "IR-04(01)"]  # sin familia AC y sin el withdrawn


def test_format_references():
    from retrieval.search import format_references

    hits = [
        {
            "text": "Block external IP address on the border firewall.",
            "ref_id": "RA2101",
            "source": "RE&CT",
            "stage": "containment",
            "url": "",
            "score": 0.81,
        }
    ]
    block = format_references(hits)
    assert "[RA2101]" in block
    assert "containment" in block


def test_save_playbook_crea_archivo(tmp_path):
    path = save_playbook("# Playbook: Ransomware\n", "Ransomware!!", output_dir=tmp_path)
    assert path.exists()
    assert path.name.startswith("playbook-ransomware-")
    assert path.read_text(encoding="utf-8").startswith("# Playbook")
