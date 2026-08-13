"""Free-text documentation (READMEs, runbooks, dashboard descriptions,
policies) linked to an asset. asset_id is nullable because some
documentation is general (e.g. a company-wide data policy) rather than
about one specific dataset.

`content` holds the full text. It is intentionally NOT chunked or
embedded here — that happens in the RAG layer (Phase 5), which reads from
this table but stores its chunks/vectors separately. Keeping the source
text and the retrieval index in different tables means the RAG pipeline
can be rebuilt (re-chunked, re-embedded) without touching source data.
"""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset import Asset


class Documentation(TimestampMixin, Base):
    __tablename__ = "documentation"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.asset_id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(60))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    asset: Mapped["Asset | None"] = relationship(back_populates="documentation")

    def __repr__(self) -> str:
        return f"Documentation(id={self.id!r}, title={self.title!r}, asset_id={self.asset_id!r})"
