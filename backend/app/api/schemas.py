"""Pydantic response models for the HTTP API.

These are deliberately separate from the SQLAlchemy models in app.models:
the ORM models describe how data is stored, these describe what the API
promises to callers. from_attributes=True lets FastAPI build a schema
directly from an ORM object (or a plain dataclass, for the composite
results like lineage/quality) without a manual field-by-field mapping.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetType, PIIStatus, QualityCheckStatus


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OwnerOut(ORMBase):
    name: str
    email: str | None
    team: str | None


class TagOut(ORMBase):
    name: str


class BusinessTermOut(ORMBase):
    term: str
    definition: str
    domain: str | None


class AssetSummaryOut(ORMBase):
    asset_id: str
    asset_name: str
    asset_type: AssetType
    domain: str | None
    pii_status: PIIStatus
    quality_score: float | None
    tags: list[TagOut] = []


class AssetDetailOut(AssetSummaryOut):
    description: str | None
    source_system: str | None
    owner: OwnerOut | None
    data_last_updated: datetime | None


class ColumnOut(ORMBase):
    column_name: str
    data_type: str
    description: str | None
    is_nullable: bool
    is_pii: bool
    pii_category: str | None
    business_term: BusinessTermOut | None


class QualityCheckOut(ORMBase):
    check_name: str
    status: QualityCheckStatus
    score: float | None
    message: str | None
    checked_at: datetime


class QualityReportOut(ORMBase):
    asset_id: str
    quality_score: float | None
    overall_status: str
    checks: list[QualityCheckOut]


class LineageHopOut(ORMBase):
    asset_id: str
    asset_name: str
    depth: int
    transformation: str | None
    description: str | None


class LineageOut(ORMBase):
    asset_id: str
    upstream: list[LineageHopOut]
    downstream: list[LineageHopOut]


class DocumentationOut(ORMBase):
    id: int
    title: str
    doc_type: str
    source_url: str | None
    asset_id: str | None
    content: str


class SearchResultsOut(BaseModel):
    assets: list[AssetSummaryOut]
    business_terms: list[BusinessTermOut]
    documentation: list[DocumentationOut]
