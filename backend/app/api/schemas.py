"""Pydantic response models for the HTTP API.

These are deliberately separate from the SQLAlchemy models in app.models:
the ORM models describe how data is stored, these describe what the API
promises to callers. from_attributes=True lets FastAPI build a schema
directly from an ORM object (or a plain dataclass, for the composite
results like lineage/quality) without a manual field-by-field mapping.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    via_asset_id: str


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


# --- Chat (Phase 11): wraps app.agent.run.run_agent()'s own return type ---
# (AgentResult/SourceRef/EvidenceItem/ToolInvocation, app/agent/state.py)
# field-for-field. No new logic lives here -- this is purely a response
# shape for the same dataclasses the agent already returns.


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class SourceRefOut(ORMBase):
    label: str
    asset_id: str | None
    source_type: str


class EvidenceItemOut(ORMBase):
    source_type: str
    title: str
    asset_id: str | None
    detail: str
    citation: str


class ToolInvocationOut(ORMBase):
    tool: str
    input: dict
    output_summary: str
    timestamp: str
    evidence_count: int


class ChatResponseOut(ORMBase):
    question: str
    answer: str
    sources: list[SourceRefOut]
    evidence: list[EvidenceItemOut]
    trace: list[ToolInvocationOut]
    grounding_status: Literal["supported", "partial", "not_supported"]


# --- Lineage graph (Phase 12): whole-catalog view, separate from the
# existing per-asset LineageOut/LineageHopOut traversal above. Backed by
# app.services.lineage.get_full_graph(), a flat dump of all assets/edges --
# a different query shape, not a duplicate of the BFS traversal. ---


class LineageGraphNodeOut(ORMBase):
    asset_id: str
    asset_name: str
    asset_type: AssetType
    domain: str | None
    pii_status: PIIStatus


class LineageGraphEdgeOut(ORMBase):
    source_asset_id: str
    target_asset_id: str
    transformation: str | None
    description: str | None


class LineageGraphOut(BaseModel):
    nodes: list[LineageGraphNodeOut]
    edges: list[LineageGraphEdgeOut]
