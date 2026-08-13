"""An owner is a person or team accountable for one or more assets.

Kept as its own table (rather than a plain string on Asset) because in a
real org the same owner is responsible for many datasets, and "who owns
this?" questions want a consistent identity (name + contact), not a
free-text string that drifts between rows.
"""
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)

    assets: Mapped[list["Asset"]] = relationship(back_populates="owner")

    def __repr__(self) -> str:
        return f"Owner(id={self.id!r}, name={self.name!r}, team={self.team!r})"
