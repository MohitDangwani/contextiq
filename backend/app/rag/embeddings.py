"""Embedding provider for the RAG pipeline.

Uses a local sentence-transformers model (all-MiniLM-L6-v2, 384-dim) so
the whole pipeline runs offline with no API key and no per-call cost.
This was chosen over the OpenAI embeddings API (part of the project's
stated tech stack) specifically because no API key was available in
this environment — see docs/rag.md for the tradeoff.

Nothing outside this module knows which provider produced a vector.
Swapping providers later means changing this file and EMBEDDING_DIM in
app/models/chunk.py, then re-running scripts/ingest_documents.py —
chunking.py and retrieval.py don't change.
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
