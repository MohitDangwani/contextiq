"""Chunks of documentation/business-term text, embedded for semantic
retrieval.

This is the RAG layer's own index, built FROM Documentation and
BusinessTerm (the source of truth, populated in Phase 3). It is fully
rebuildable — clearing and re-ingesting document_chunks never loses any
real data, because none lives here. Kept in app/models/ (not app/rag/)
because it's still just a table description; app/rag/ holds the
pipeline logic that reads and writes it.
"""
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# sentence-transformers/all-MiniLM-L6-v2 output dimension. Changing the
# embedding model requires changing this and re-running ingestion.
EMBEDDING_DIM = 384


class ChunkSourceType(str, enum.Enum):
    DOCUMENTATION = "documentation"
    BUSINESS_TERM = "business_term"


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Polymorphic reference: source_id means documentation.id when
    # source_type is DOCUMENTATION, business_terms.id when BUSINESS_TERM.
    # Not a real FK -- two possible parent tables -- but source_type
    # always disambiguates it for any caller that needs to look the row up.
    source_type: Mapped[ChunkSourceType] = mapped_column(
        Enum(ChunkSourceType, name="chunk_source_type", values_callable=lambda e: [m.value for m in e])
    )
    source_id: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)

    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    # Denormalized citation metadata: lets a retrieved chunk be traced
    # back to its source (title, owning asset, external link) without an
    # extra join at query time.
    title: Mapped[str] = mapped_column(String(200))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.asset_id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return (
            f"DocumentChunk(id={self.id!r}, source_type={self.source_type!r}, "
            f"source_id={self.source_id!r}, chunk_index={self.chunk_index!r})"
        )
