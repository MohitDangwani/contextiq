"""Asset is the central entity of the context layer: one row per dataset
(table, view, dashboard, or model) that the agent can be asked about.
Everything else in this package (columns, quality checks, lineage,
documentation, tags) hangs off an Asset.

asset_id is a human-readable slug (e.g. "customer_orders") rather than a
surrogate integer, because it doubles as the stable identifier used in
lineage edges, documentation links, and agent tool calls/citations — an
interviewer-friendly "just read the FK" experience.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AssetType, PIIStatus
from app.models.tag import asset_tags

if TYPE_CHECKING:
    from app.models.column import DatasetColumn
    from app.models.documentation import Documentation
    from app.models.lineage import LineageEdge
    from app.models.owner import Owner
    from app.models.quality import DataQualityCheck
    from app.models.tag import Tag


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    asset_name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", values_callable=lambda e: [m.value for m in e])
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(120), nullable=True)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True)
    owner: Mapped["Owner | None"] = relationship(back_populates="assets")

    pii_status: Mapped[PIIStatus] = mapped_column(
        Enum(PIIStatus, name="pii_status", values_callable=lambda e: [m.value for m in e]),
        default=PIIStatus.UNKNOWN,
    )
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_last_updated: Mapped[datetime | None] = mapped_column(nullable=True)

    tags: Mapped[list["Tag"]] = relationship(secondary=asset_tags, back_populates="assets")
    columns: Mapped[list["DatasetColumn"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    quality_checks: Mapped[list["DataQualityCheck"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    documentation: Mapped[list["Documentation"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )

    # Lineage is asset-to-asset, so an Asset can be the source of edges
    # flowing "downstream" and the target of edges flowing in "upstream".
    lineage_downstream: Mapped[list["LineageEdge"]] = relationship(
        foreign_keys="LineageEdge.source_asset_id", back_populates="source_asset"
    )
    lineage_upstream: Mapped[list["LineageEdge"]] = relationship(
        foreign_keys="LineageEdge.target_asset_id", back_populates="target_asset"
    )

    def __repr__(self) -> str:
        return f"Asset(asset_id={self.asset_id!r}, asset_name={self.asset_name!r})"
