"""Individual data-quality checks for an asset (freshness, completeness,
uniqueness, validity, ...). Modeled as a history of discrete checks rather
than a single score so "is this dataset trustworthy?" can be answered with
specifics ("freshness check failed 2 days ago: no new rows since...")
instead of just a number.

Asset.quality_score remains as a fast, top-line rollup for search/filter;
these rows are the evidence behind it.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import QualityCheckStatus

if TYPE_CHECKING:
    from app.models.asset import Asset


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    check_name: Mapped[str] = mapped_column(String(60))
    status: Mapped[QualityCheckStatus] = mapped_column(
        Enum(QualityCheckStatus, name="quality_check_status", values_callable=lambda e: [m.value for m in e])
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    asset: Mapped["Asset"] = relationship(back_populates="quality_checks")

    def __repr__(self) -> str:
        return f"DataQualityCheck(asset_id={self.asset_id!r}, check_name={self.check_name!r}, status={self.status!r})"
