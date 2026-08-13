"""Column-level metadata for an asset. Named DatasetColumn (not Column) to
avoid clashing with sqlalchemy.Column, and table name dataset_columns for
the same reason.

PII is tracked at both the asset level (Asset.pii_status, a fast top-line
filter — "which datasets contain PII?") and the column level (is_pii,
pii_category — the actual detail: which column, what kind of PII).
"""
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.business_term import BusinessTerm


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    column_name: Mapped[str] = mapped_column(String(120))
    data_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)

    is_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_category: Mapped[str | None] = mapped_column(String(60), nullable=True)

    business_term_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_terms.id"), nullable=True
    )

    asset: Mapped["Asset"] = relationship(back_populates="columns")
    business_term: Mapped["BusinessTerm | None"] = relationship(back_populates="columns")

    def __repr__(self) -> str:
        return f"DatasetColumn(asset_id={self.asset_id!r}, column_name={self.column_name!r})"
