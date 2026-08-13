"""A business term is a named, agreed-upon definition (e.g. what does
"customer_lifetime_value" actually mean?). Stored separately from Column
because the same term can apply to columns across multiple datasets, and
because "what does X mean?" is a distinct question from "what columns
exist?" — the agent should be able to answer it even without first
knowing which table the user is asking about.
"""
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.column import DatasetColumn


class BusinessTerm(TimestampMixin, Base):
    __tablename__ = "business_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(120), unique=True)
    definition: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(60), nullable=True)

    columns: Mapped[list["DatasetColumn"]] = relationship(back_populates="business_term")

    def __repr__(self) -> str:
        return f"BusinessTerm(id={self.id!r}, term={self.term!r})"
