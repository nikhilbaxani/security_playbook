"""Ingesta del conocimiento de referencia: descarga las fuentes públicas,
las trocea en chunks con metadata (ID citable, fase, fuente) y las vectoriza
en una base Chroma local.

Fuentes:
  - RE&CT (atc-project): 216 acciones de respuesta a incidentes, JSON estructurado
  - NIST SP 800-53 Rev 5 (OSCAL): familias IR (Incident Response) y CP (Contingency Planning)
  - NIST SP 800-61 Rev 2: PDF oficial, troceado por página

Uso:
    python -m retrieval.ingest
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = PROJECT_ROOT / "reference"
DB_DIR = REFERENCE_DIR / "chroma_db"
COLLECTION_NAME = "ir_knowledge"

SOURCES = {
    "react.json": "https://raw.githubusercontent.com/atc-project/atc-react/master/docs/react.json",
    "NIST_SP-800-53_rev5_catalog.json": "https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json",
    "NIST.SP.800-61r2.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf",
}

# Modelo multilingüe: las fuentes están en inglés pero las consultas llegan en español.
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


# ---------------------------------------------------------------- descarga

def download_sources(dest_dir: Path = REFERENCE_DIR) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in SOURCES.items():
        dest = dest_dir / filename
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  [ok] {filename} ya descargado")
            continue
        print(f"  [..] descargando {filename}")
        # nvlpubs.nist.gov devuelve 403 al user-agent por defecto de urllib
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            dest.write_bytes(response.read())


# ---------------------------------------------------------------- chunkers

def react_to_chunks(stix: dict) -> list[dict]:
    """Una acción RE&CT (x-react-action) = un chunk, con su ID RA#### citable."""
    chunks = []
    for obj in stix.get("objects", []):
        if obj.get("type") != "x-react-action":
            continue
        refs = obj.get("external_references", [])
        ext = next((r for r in refs if r.get("external_id", "").startswith("RA")), {})
        ref_id = ext.get("external_id")
        if not ref_id or not obj.get("description"):
            continue
        stages = [p["phase_name"] for p in obj.get("kill_chain_phases", [])]
        chunks.append(
            {
                "id": f"react-{ref_id}",
                "text": f"{obj['name']}. {obj['description'].strip()}",
                "metadata": {
                    "source": "RE&CT",
                    "ref_id": ref_id,
                    "stage": ", ".join(stages),
                    "url": ext.get("url", ""),
                },
            }
        )
    return chunks


def _control_prose(control: dict) -> str:
    acc: list[str] = []

    def walk(parts):
        for part in parts:
            prose = part.get("prose")
            if prose and part.get("name") != "guidance":
                acc.append(prose)
            walk(part.get("parts", []))

    walk(control.get("parts", []))
    text = " ".join(acc)
    # los parámetros OSCAL aparecen como "{{ insert: param, ir-1_prm_1 }}"
    return re.sub(r"\{\{[^}]*\}\}", "[definido por la organización]", text)


def _is_withdrawn(control: dict) -> bool:
    return any(
        p.get("name") == "status" and p.get("value") == "withdrawn"
        for p in control.get("props", [])
    )


def oscal_to_chunks(catalog: dict, families: tuple[str, ...] = ("ir", "cp")) -> list[dict]:
    """Un control (o mejora de control) de NIST 800-53 = un chunk, con su ID (ej. IR-4)."""
    chunks = []

    def add_control(control: dict, family_title: str):
        if _is_withdrawn(control):
            return
        text = _control_prose(control)
        if not text.strip():
            return
        label = next(
            (p["value"] for p in control.get("props", []) if p["name"] == "label"),
            control["id"].upper(),
        )
        chunks.append(
            {
                "id": f"sp80053-{control['id']}",
                "text": f"{control['title']}. {text}",
                "metadata": {
                    "source": "NIST SP 800-53 r5",
                    "ref_id": label,
                    "stage": family_title,
                    "url": f"https://csrc.nist.gov/projects/cprt (control {label})",
                },
            }
        )
        for enhancement in control.get("controls", []):
            add_control(enhancement, family_title)

    for group in catalog["catalog"]["groups"]:
        if group["id"] not in families:
            continue
        for control in group.get("controls", []):
            add_control(control, group["title"])
    return chunks


def pdf_to_chunks(pdf_path: Path, source_name: str = "NIST SP 800-61 r2") -> list[dict]:
    """Una página del PDF = un chunk (se saltan páginas casi vacías: portada, índices)."""
    import pdfplumber

    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            if len(text) < 300:
                continue
            chunks.append(
                {
                    "id": f"sp80061-p{page.page_number}",
                    "text": text,
                    "metadata": {
                        "source": source_name,
                        "ref_id": f"800-61 p.{page.page_number}",
                        "stage": "",
                        "url": SOURCES["NIST.SP.800-61r2.pdf"],
                    },
                }
            )
    return chunks


def build_all_chunks(reference_dir: Path = REFERENCE_DIR) -> list[dict]:
    react = json.loads((reference_dir / "react.json").read_text(encoding="utf-8"))
    oscal = json.loads(
        (reference_dir / "NIST_SP-800-53_rev5_catalog.json").read_text(encoding="utf-8")
    )
    chunks = react_to_chunks(react)
    chunks += oscal_to_chunks(oscal)
    chunks += pdf_to_chunks(reference_dir / "NIST.SP.800-61r2.pdf")
    return chunks


# ---------------------------------------------------------------- indexado

def index_chunks(chunks: list[dict], db_dir: Path = DB_DIR) -> None:
    import os

    import chromadb
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    print(f"  [..] cargando modelo de embeddings: {model_name}")
    model = SentenceTransformer(model_name)

    client = chromadb.PersistentClient(path=str(db_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    print(f"  [..] vectorizando {len(chunks)} chunks")
    batch = 64
    for start in range(0, len(chunks), batch):
        part = chunks[start : start + batch]
        embeddings = model.encode([c["text"] for c in part], show_progress_bar=False)
        collection.add(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            metadatas=[c["metadata"] for c in part],
            embeddings=[e.tolist() for e in embeddings],
        )
        print(f"       {min(start + batch, len(chunks))}/{len(chunks)}")
    print(f"  [ok] índice creado en {db_dir}")


def main() -> None:
    print("1/3 Descargando fuentes públicas...")
    download_sources()
    print("2/3 Troceando en chunks con metadata...")
    chunks = build_all_chunks()
    by_source: dict[str, int] = {}
    for c in chunks:
        by_source[c["metadata"]["source"]] = by_source.get(c["metadata"]["source"], 0) + 1
    for source, count in by_source.items():
        print(f"  {source}: {count} chunks")
    print("3/3 Vectorizando e indexando en Chroma...")
    index_chunks(chunks)


if __name__ == "__main__":
    sys.exit(main())
