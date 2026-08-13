"""Shared SQLAlchemy declarative base and mixins used by every model."""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """created_at/updated_at for the metadata *record itself* (audit trail).

    Not to be confused with an asset's data_last_updated, which tracks when
    the underlying dataset was refreshed in its source system.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
