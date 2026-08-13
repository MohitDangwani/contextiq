"""Import every model so they register on Base.metadata — required for
Base.metadata.create_all() (and later, Alembic autogenerate) to see them.
"""
from app.models.base import Base
from app.models.owner import Owner
from app.models.tag import Tag, asset_tags
from app.models.business_term import BusinessTerm
from app.models.asset import Asset
from app.models.column import DatasetColumn
from app.models.lineage import LineageEdge
from app.models.quality import DataQualityCheck
from app.models.documentation import Documentation
from app.models.chunk import ChunkSourceType, DocumentChunk

__all__ = [
    "Base",
    "Owner",
    "Tag",
    "asset_tags",
    "BusinessTerm",
    "Asset",
    "DatasetColumn",
    "LineageEdge",
    "DataQualityCheck",
    "Documentation",
    "ChunkSourceType",
    "DocumentChunk",
]
