"""Core asset lookups: search, full metadata, schema, and ownership.

Every other service (lineage, quality, documentation) assumes the caller
already has a valid asset_id — usually obtained from search_assets or a
direct get_asset call here first.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, DatasetColumn, Owner
from app.models.enums import AssetType, PIIStatus


def search_assets(
    db: Session,
    query: str | None = None,
    domain: str | None = None,
    asset_type: AssetType | None = None,
    tag: str | None = None,
    pii_only: bool = False,
    limit: int = 50,
) -> list[Asset]:
    """Keyword + filter search over assets. All filters are optional and
    combine with AND; `query` matches against asset_name/description."""
    stmt = db.query(Asset).options(selectinload(Asset.owner), selectinload(Asset.tags))

    if query:
        like = f"%{query}%"
        stmt = stmt.filter(or_(Asset.asset_name.ilike(like), Asset.description.ilike(like)))
    if domain:
        stmt = stmt.filter(Asset.domain == domain)
    if asset_type:
        stmt = stmt.filter(Asset.asset_type == asset_type)
    if tag:
        stmt = stmt.filter(Asset.tags.any(name=tag))
    if pii_only:
        stmt = stmt.filter(Asset.pii_status == PIIStatus.CONTAINS_PII)

    return stmt.order_by(Asset.asset_id).limit(limit).all()


def get_asset(db: Session, asset_id: str) -> Asset | None:
    """Full metadata for one asset, including owner and tags."""
    return (
        db.query(Asset)
        .options(selectinload(Asset.owner), selectinload(Asset.tags))
        .filter(Asset.asset_id == asset_id)
        .one_or_none()
    )


def get_schema(db: Session, asset_id: str) -> list[DatasetColumn] | None:
    """Column list for an asset. Returns None if the asset itself doesn't
    exist (distinct from an empty list, which means the asset exists but
    has no modeled columns — e.g. a BI dashboard)."""
    if db.get(Asset, asset_id) is None:
        return None
    return (
        db.query(DatasetColumn)
        .options(selectinload(DatasetColumn.business_term))
        .filter(DatasetColumn.asset_id == asset_id)
        .order_by(DatasetColumn.id)
        .all()
    )


def get_owner(db: Session, asset_id: str) -> Owner | None:
    """The owner of an asset. Returns None both when the asset doesn't
    exist and when it has no owner recorded — callers that need to tell
    those apart should call get_asset first."""
    asset = (
        db.query(Asset)
        .options(selectinload(Asset.owner))
        .filter(Asset.asset_id == asset_id)
        .one_or_none()
    )
    return asset.owner if asset else None
