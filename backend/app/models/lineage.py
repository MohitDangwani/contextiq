"""Asset-to-asset lineage edges, e.g. customers -> orders -> order_items ->
revenue_model -> monthly_revenue -> revenue_dashboard.

Kept at asset granularity (not column-level) deliberately: it answers the
product's actual questions ("where does revenue come from?", "which
tables feed the revenue dashboard?") without the extra modeling and
ingestion cost of column-level lineage, which this prototype doesn't need.
"""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset import Asset


class LineageEdge(TimestampMixin, Base):
    __tablename__ = "lineage_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    target_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    transformation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_asset: Mapped["Asset"] = relationship(
        foreign_keys=[source_asset_id], back_populates="lineage_downstream"
    )
    target_asset: Mapped["Asset"] = relationship(
        foreign_keys=[target_asset_id], back_populates="lineage_upstream"
    )

    def __repr__(self) -> str:
        return f"LineageEdge({self.source_asset_id!r} -> {self.target_asset_id!r})"
