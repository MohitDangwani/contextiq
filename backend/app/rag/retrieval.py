"""Builds and queries the RAG index (app.models.chunk.DocumentChunk).

Ingestion reads from Documentation and BusinessTerm — the source of
truth, populated in Phase 3 — and is safe to re-run: it clears and
rebuilds document_chunks from scratch every time, the same way
scripts/seed_database.py rebuilds the catalog. Nothing here is called by
app/api or app/services yet; this module is used directly by
scripts/ingest_documents.py and scripts/test_retrieval.py until the
agent (Phase 7/8) needs semantic_search as a tool.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import BusinessTerm, Documentation
from app.models.chunk import ChunkSourceType, DocumentChunk
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_batch


def clear_chunks(db: Session) -> None:
    db.query(DocumentChunk).delete()
    db.commit()


def ingest_documentation(db: Session) -> int:
    """Chunk + embed every Documentation row. Returns the chunk count."""
    count = 0
    for doc in db.query(Documentation).all():
        pieces = chunk_text(doc.content)
        if not pieces:
            continue
        vectors = embed_batch(pieces)
        for i, (piece, vector) in enumerate(zip(pieces, vectors)):
            db.add(DocumentChunk(
                source_type=ChunkSourceType.DOCUMENTATION,
                source_id=doc.id,
                chunk_index=i,
                content=piece,
                embedding=vector,
                title=doc.title,
                asset_id=doc.asset_id,
                source_url=doc.source_url,
            ))
            count += 1
    return count


def ingest_business_terms(db: Session) -> int:
    """Chunk + embed every BusinessTerm row. The term name is folded into
    the embedded text (f"{term}: {definition}") so a query using the
    term itself, not just its definition, still matches well."""
    count = 0
    for term in db.query(BusinessTerm).all():
        combined = f"{term.term}: {term.definition}"
        pieces = chunk_text(combined)
        vectors = embed_batch(pieces)
        for i, (piece, vector) in enumerate(zip(pieces, vectors)):
            db.add(DocumentChunk(
                source_type=ChunkSourceType.BUSINESS_TERM,
                source_id=term.id,
                chunk_index=i,
                content=piece,
                embedding=vector,
                title=f"Business term: {term.term}",
                asset_id=None,
                source_url=None,
            ))
            count += 1
    return count


@dataclass
class RetrievedChunk:
    chunk_id: int
    content: str
    title: str
    source_type: str
    asset_id: str | None
    source_url: str | None
    similarity: float


def semantic_search(
    db: Session, query: str, k: int = 5, asset_id: str | None = None
) -> list[RetrievedChunk]:
    """Embed `query` and return the k nearest chunks by cosine similarity.

    similarity = 1 - cosine_distance, so 1.0 is an exact match and 0.0 is
    orthogonal. asset_id, if given, restricts results to chunks tied to
    that asset (documentation only — business terms have no asset_id).
    """
    query_vector = embed_batch([query])[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vector)

    stmt = db.query(DocumentChunk, distance.label("distance"))
    if asset_id:
        stmt = stmt.filter(DocumentChunk.asset_id == asset_id)
    rows = stmt.order_by(distance).limit(k).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            content=chunk.content,
            title=chunk.title,
            source_type=chunk.source_type.value,
            asset_id=chunk.asset_id,
            source_url=chunk.source_url,
            similarity=1 - dist,
        )
        for chunk, dist in rows
    ]
