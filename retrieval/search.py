"""Búsqueda semántica sobre el índice de conocimiento (RE&CT + NIST 800-53 + NIST 800-61)."""

import os
from pathlib import Path

from .ingest import COLLECTION_NAME, DB_DIR, DEFAULT_EMBEDDING_MODEL


class RetrievalError(RuntimeError):
    pass


class Retriever:
    def __init__(self, db_dir: Path | None = None, model_name: str | None = None):
        db_dir = db_dir or DB_DIR
        if not db_dir.exists():
            raise RetrievalError(
                "No existe el índice vectorial. Créalo primero con: python -m retrieval.ingest"
            )
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RetrievalError(
                "Dependencias de RAG no instaladas. Ejecuta: "
                "pip install sentence-transformers chromadb pdfplumber"
            ) from exc
        self._model = SentenceTransformer(
            model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        )
        client = chromadb.PersistentClient(path=str(db_dir))
        try:
            self._collection = client.get_collection(COLLECTION_NAME)
        except Exception as exc:
            raise RetrievalError(
                f"El índice existe pero no contiene la colección '{COLLECTION_NAME}'. "
                "Reconstrúyelo con: python -m retrieval.ingest"
            ) from exc

    def search(self, query: str, top_k: int = 10, source: str | None = None) -> list[dict]:
        embedding = self._model.encode([query])[0].tolist()
        where = {"source": source} if source else None
        result = self._collection.query(
            query_embeddings=[embedding], n_results=top_k, where=where
        )
        hits = []
        for doc, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            hits.append(
                {
                    "text": doc,
                    "ref_id": meta["ref_id"],
                    "source": meta["source"],
                    "stage": meta.get("stage", ""),
                    "url": meta.get("url", ""),
                    "score": round(1 - distance, 3),
                }
            )
        return hits


def format_references(hits: list[dict], max_chars_per_hit: int = 900) -> str:
    """Bloque Markdown con las referencias recuperadas, listo para inyectar en el prompt."""
    lines = []
    for hit in hits:
        stage = f" | etapa: {hit['stage']}" if hit["stage"] else ""
        text = hit["text"]
        if len(text) > max_chars_per_hit:
            text = text[:max_chars_per_hit] + "…"
        lines.append(f"### [{hit['ref_id']}] ({hit['source']}{stage})\n{text}\n")
    return "\n".join(lines)
