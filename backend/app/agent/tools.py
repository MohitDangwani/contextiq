"""Agent tool layer: thin wrappers around the Phase 4 services and the
Phase 5 semantic_search. Every wrapper does two things: (1) return a
short natural-language summary the LLM can read as a tool result, and
(2) return structured EvidenceItem entries the graph uses to build
citations -- so the final answer's sources come from what each tool
actually returned, never from trusting the LLM's self-report.

No query/business logic is duplicated here -- every _run_* function is a
thin formatter around a call into app.services.* or app.rag.retrieval.
"""
from dataclasses import dataclass
from typing import Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.state import EvidenceItem, ToolResult
from app.models import Asset
from app.rag.retrieval import semantic_search
from app.services import assets as assets_service
from app.services import business_terms as business_term_service
from app.services import lineage as lineage_service
from app.services import quality as quality_service

# Below this cosine-similarity score, a RAG hit is treated as noise
# rather than evidence -- prevents the agent from citing a barely-related
# document just because it was the least-bad match in the index.
DOC_SIMILARITY_THRESHOLD = 0.35


def _known_asset_ids(db: Session) -> list[str]:
    return [a.asset_id for a in db.query(Asset.asset_id).order_by(Asset.asset_id).all()]


def _not_found(db: Session, asset_id: str) -> ToolResult:
    known = ", ".join(_known_asset_ids(db))
    return ToolResult(
        summary=f"No dataset with id '{asset_id}' exists in the ContextIQ catalog. Known dataset ids: {known}.",
        evidence=[],
    )


# ---------------------------------------------------------------------------
# search_assets
# ---------------------------------------------------------------------------

class SearchAssetsArgs(BaseModel):
    query: str | None = Field(None, description="Keyword to match against dataset name/description.")
    pii_only: bool = Field(False, description="If true, only return datasets that contain PII.")
    owner: str | None = Field(
        None, description="Filter to datasets owned by this team/person (substring match)."
    )
    domain: str | None = Field(
        None, description="Filter to datasets in this business domain, e.g. 'sales', 'finance', 'marketing'."
    )
    tag: str | None = Field(None, description="Filter to datasets tagged with this label.")


def _run_search_assets(
    db: Session,
    query: str | None = None,
    pii_only: bool = False,
    owner: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
) -> ToolResult:
    results = assets_service.search_assets(
        db, query=query, pii_only=pii_only, owner=owner, domain=domain, tag=tag, limit=20
    )
    if not results:
        return ToolResult(summary="No datasets matched those filters.", evidence=[])
    lines, evidence = [], []
    for a in results:
        owner_name = a.owner.name if a.owner else "no recorded owner"
        line = (
            f"{a.asset_id} ({a.asset_name}): type={a.asset_type.value}, domain={a.domain}, "
            f"pii_status={a.pii_status.value}, owner={owner_name}, quality_score={a.quality_score}"
        )
        lines.append(f"- {line}")
        evidence.append(EvidenceItem(
            source_type="asset", title=a.asset_name, asset_id=a.asset_id,
            detail=line, citation=f"{a.asset_id} (catalog metadata)",
        ))
    return ToolResult(summary="Matching datasets:\n" + "\n".join(lines), evidence=evidence)


# ---------------------------------------------------------------------------
# get_schema
# ---------------------------------------------------------------------------

class AssetIdArgs(BaseModel):
    asset_id: str = Field(
        ...,
        description="The dataset's catalog id, e.g. 'orders', 'customers', 'revenue_dashboard'. "
        "Use search_assets first if you don't know the exact id.",
    )


def _run_get_schema(db: Session, asset_id: str) -> ToolResult:
    columns = assets_service.get_schema(db, asset_id)
    if columns is None:
        return _not_found(db, asset_id)
    if not columns:
        return ToolResult(
            summary=f"'{asset_id}' has no modeled columns (e.g. it may be a dashboard, not a table).",
            evidence=[],
        )
    lines, evidence = [], []
    for c in columns:
        pii_note = f", PII ({c.pii_category})" if c.is_pii else ""
        line = f"{c.column_name}: {c.data_type}{pii_note}"
        lines.append(f"- {line}")
        evidence.append(EvidenceItem(
            source_type="schema", title=f"{asset_id}.{c.column_name}", asset_id=asset_id,
            detail=line, citation=f"{asset_id} schema (catalog metadata)",
        ))
    return ToolResult(summary=f"Schema for '{asset_id}':\n" + "\n".join(lines), evidence=evidence)


# ---------------------------------------------------------------------------
# get_owner
# ---------------------------------------------------------------------------

def _run_get_owner(db: Session, asset_id: str) -> ToolResult:
    asset = assets_service.get_asset(db, asset_id)
    if asset is None:
        return _not_found(db, asset_id)
    if asset.owner is None:
        return ToolResult(summary=f"'{asset_id}' has no recorded owner.", evidence=[])
    o = asset.owner
    detail = (
        f"{asset_id} is owned by {o.name}"
        + (f" ({o.team} team)" if o.team else "")
        + (f", contact {o.email}" if o.email else "")
    )
    return ToolResult(
        summary=detail,
        evidence=[EvidenceItem(
            source_type="owner", title=o.name, asset_id=asset_id,
            detail=detail, citation=f"{asset_id} ownership (catalog metadata)",
        )],
    )


# ---------------------------------------------------------------------------
# check_pii
# ---------------------------------------------------------------------------

class PiiCheckArgs(BaseModel):
    asset_id: str | None = Field(
        None,
        description="Dataset id to check for PII. Omit entirely to list ALL datasets in the "
        "catalog that contain PII.",
    )


def _run_check_pii(db: Session, asset_id: str | None = None) -> ToolResult:
    if asset_id:
        asset = assets_service.get_asset(db, asset_id)
        if asset is None:
            return _not_found(db, asset_id)
        columns = assets_service.get_schema(db, asset_id) or []
        pii_cols = [c for c in columns if c.is_pii]
        if not pii_cols:
            detail = f"{asset_id} pii_status={asset.pii_status.value}, no PII columns."
            return ToolResult(
                summary=f"'{asset_id}' does not contain PII (pii_status={asset.pii_status.value}).",
                evidence=[EvidenceItem(
                    source_type="pii", title=asset.asset_name, asset_id=asset_id,
                    detail=detail, citation=f"{asset_id} (catalog metadata)",
                )],
            )
        cols_desc = ", ".join(f"{c.column_name} ({c.pii_category})" for c in pii_cols)
        detail = f"'{asset_id}' contains PII in columns: {cols_desc}."
        return ToolResult(
            summary=detail,
            evidence=[EvidenceItem(
                source_type="pii", title=asset.asset_name, asset_id=asset_id,
                detail=detail, citation=f"{asset_id} schema (catalog metadata)",
            )],
        )

    results = assets_service.search_assets(db, pii_only=True, limit=50)
    if not results:
        return ToolResult(summary="No datasets in the catalog are marked as containing PII.", evidence=[])
    lines, evidence = [], []
    for a in results:
        lines.append(f"- {a.asset_id} ({a.asset_name})")
        evidence.append(EvidenceItem(
            source_type="pii", title=a.asset_name, asset_id=a.asset_id,
            detail=f"{a.asset_id} contains PII.", citation=f"{a.asset_id} (catalog metadata)",
        ))
    return ToolResult(summary="Datasets containing PII:\n" + "\n".join(lines), evidence=evidence)


# ---------------------------------------------------------------------------
# get_lineage
# ---------------------------------------------------------------------------

class LineageArgs(BaseModel):
    asset_id: str = Field(..., description="The dataset's catalog id.")
    direction: Literal["upstream", "downstream", "both"] = Field(
        "both",
        description="'upstream' = datasets that feed INTO this one (use for 'where does X come "
        "from'); 'downstream' = datasets this one feeds INTO (use for 'what depends on X'); "
        "'both' for the full picture.",
    )


def _run_get_lineage(db: Session, asset_id: str, direction: str = "both") -> ToolResult:
    result = lineage_service.get_lineage(db, asset_id, direction=direction)
    if result is None:
        return _not_found(db, asset_id)
    if not result.upstream and not result.downstream:
        return ToolResult(summary=f"'{asset_id}' has no recorded lineage in either direction.", evidence=[])

    lines, evidence = [], []
    if result.upstream:
        lines.append("Upstream (feeds into this dataset):")
        for hop in sorted(result.upstream, key=lambda h: h.depth):
            # State this hop's OWN edge endpoints explicitly (not just "N hops
            # away via TRANSFORMATION") so a multi-hop chain can't have a
            # transformation from one edge misattributed to an adjacent one
            # when it's narrated as a sequential path.
            line = (
                f"  - {hop.asset_id} ({hop.asset_name}), {hop.depth} hop(s) upstream. "
                f"Direct edge for this hop: {hop.asset_id} -> {hop.via_asset_id}, via: {hop.transformation}"
            )
            lines.append(line)
            evidence.append(EvidenceItem(
                source_type="lineage", title=hop.asset_name, asset_id=hop.asset_id,
                detail=line.strip(), citation=f"lineage: {hop.asset_id} -> {hop.via_asset_id}",
            ))
    if result.downstream:
        lines.append("Downstream (this dataset feeds into):")
        for hop in sorted(result.downstream, key=lambda h: h.depth):
            line = (
                f"  - {hop.asset_id} ({hop.asset_name}), {hop.depth} hop(s) downstream. "
                f"Direct edge for this hop: {hop.via_asset_id} -> {hop.asset_id}, via: {hop.transformation}"
            )
            lines.append(line)
            evidence.append(EvidenceItem(
                source_type="lineage", title=hop.asset_name, asset_id=hop.asset_id,
                detail=line.strip(), citation=f"lineage: {hop.via_asset_id} -> {hop.asset_id}",
            ))
    return ToolResult(summary=f"Lineage for '{asset_id}':\n" + "\n".join(lines), evidence=evidence)


# ---------------------------------------------------------------------------
# check_quality
# ---------------------------------------------------------------------------

def _run_check_quality(db: Session, asset_id: str) -> ToolResult:
    result = quality_service.check_data_quality(db, asset_id)
    if result is None:
        return _not_found(db, asset_id)
    if not result.checks:
        return ToolResult(
            summary=f"'{asset_id}' has no recorded quality checks (overall status: unknown).", evidence=[]
        )
    lines, evidence = [], []
    for c in result.checks:
        line = f"{c.check_name}: {c.status.value.upper()} (score={c.score}) — {c.message}"
        lines.append(f"- {line}")
        evidence.append(EvidenceItem(
            source_type="quality", title=f"{asset_id} {c.check_name}", asset_id=asset_id,
            detail=line, citation=f"{asset_id} quality check: {c.check_name}",
        ))
    summary = (
        f"Quality for '{asset_id}' (overall: {result.overall_status.upper()}, "
        f"quality_score={result.quality_score}):\n" + "\n".join(lines)
    )
    return ToolResult(summary=summary, evidence=evidence)


# ---------------------------------------------------------------------------
# get_business_definition
# ---------------------------------------------------------------------------

class BusinessTermArgs(BaseModel):
    term: str = Field(
        ..., description="The business term or metric to define, e.g. 'customer lifetime value', 'net revenue'."
    )


def _run_get_business_definition(db: Session, term: str) -> ToolResult:
    result = business_term_service.get_business_definition(db, term.strip().replace(" ", "_"))
    if result is None:
        candidates = business_term_service.search_business_terms(db, term, limit=3)
        result = candidates[0] if candidates else None
    if result is None:
        return ToolResult(summary=f"No business term matching '{term}' was found in ContextIQ.", evidence=[])
    detail = f"{result.term}: {result.definition}"
    return ToolResult(
        summary=detail,
        evidence=[EvidenceItem(
            source_type="business_term", title=result.term, asset_id=None,
            detail=detail, citation=f"business term: {result.term}",
        )],
    )


# ---------------------------------------------------------------------------
# search_documentation (RAG)
# ---------------------------------------------------------------------------

class DocSearchArgs(BaseModel):
    query: str = Field(..., description="Free-text search query for documentation/policies not covered by the other tools.")
    asset_id: str | None = Field(None, description="Restrict the search to documentation about this dataset.")


def _run_search_documentation(db: Session, query: str, asset_id: str | None = None) -> ToolResult:
    hits = semantic_search(db, query, k=5, asset_id=asset_id)
    hits = [h for h in hits if h.similarity >= DOC_SIMILARITY_THRESHOLD]
    if not hits:
        return ToolResult(summary=f"No documentation found relevant to '{query}'.", evidence=[])
    lines, evidence = [], []
    for h in hits:
        lines.append(f"- [{h.title}] {h.content}")
        evidence.append(EvidenceItem(
            source_type="documentation", title=h.title, asset_id=h.asset_id,
            detail=h.content, citation=h.source_url or h.title,
        ))
    return ToolResult(summary="Relevant documentation:\n" + "\n".join(lines), evidence=evidence)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    tool: StructuredTool  # bound to the LLM for its name/description/schema only
    run: Callable[..., ToolResult]  # actually executed by the graph


def _sanitize_args(kwargs: dict) -> dict:
    """Some LLM tool-calling clients (observed with Nemotron 3 Nano via LM
    Studio) serialize an omitted/optional argument as the literal string
    "None" instead of leaving it out or using JSON null. Left as is, that
    string is then used as a real filter value (asset_id="None",
    query="None", ...), which silently matches nothing and gets misread as
    "there is no such data in ContextIQ" -- a false negative caused by a
    malformed tool call, not a genuine absence of evidence. Coerce it back
    to a real None here, at the tool dispatch boundary, before it reaches
    any _run_* function."""
    return {
        k: (None if isinstance(v, str) and v.strip().lower() in ("none", "null") else v)
        for k, v in kwargs.items()
    }


def build_tool_specs(db: Session) -> dict[str, ToolSpec]:
    """One ToolSpec per agent capability, bound to this specific DB
    session. Call once per agent run (see app/agent/run.py) -- tools are
    not shared/reused across runs since each run should see a consistent
    snapshot of the database for the duration of its own session."""
    specs: dict[str, ToolSpec] = {}

    def register(name, description, args_schema, run_fn):
        lc_tool = StructuredTool.from_function(
            name=name,
            description=description,
            args_schema=args_schema,
            func=lambda **kw: run_fn(db, **_sanitize_args(kw)).summary,
        )
        specs[name] = ToolSpec(tool=lc_tool, run=lambda **kw: run_fn(db, **_sanitize_args(kw)))

    register(
        "search_assets",
        "Search/filter ContextIQ's data catalog for datasets by keyword, PII status, owning "
        "team, domain, or tag. Use this to find which dataset a question is about, or to "
        "answer broad questions like 'which datasets contain PII' or 'which datasets does "
        "<team> own'. Filters combine: e.g. pii_only=true with owner='Sales Engineering' "
        "answers 'which PII datasets does Sales Engineering own' in one call.",
        SearchAssetsArgs, _run_search_assets,
    )
    register("get_schema", "Get the column-level schema for a specific dataset.", AssetIdArgs, _run_get_schema)
    register("get_owner", "Get the owning team/person for a specific dataset.", AssetIdArgs, _run_get_owner)
    register(
        "check_pii",
        "Check PII status for a specific dataset (asset_id given), or list every dataset in "
        "the catalog that contains PII (asset_id omitted).",
        PiiCheckArgs, _run_check_pii,
    )
    register(
        "get_lineage",
        "Get upstream/downstream data lineage for a dataset -- what feeds into it and/or what "
        "it feeds into.",
        LineageArgs, _run_get_lineage,
    )
    register(
        "check_quality",
        "Get recorded data quality checks and an overall trust verdict (pass/warn/fail) for a "
        "dataset. Use this for 'is X trustworthy/reliable' questions.",
        AssetIdArgs, _run_check_quality,
    )
    register(
        "get_business_definition",
        "Look up the definition of a business term or metric, e.g. 'customer lifetime value'.",
        BusinessTermArgs, _run_get_business_definition,
    )
    register(
        "search_documentation",
        "Semantic search over ContextIQ's documentation and policies, for free-text questions "
        "not covered by the other tools (e.g. general policies, dashboard descriptions, refresh "
        "schedules).",
        DocSearchArgs, _run_search_documentation,
    )

    return specs
