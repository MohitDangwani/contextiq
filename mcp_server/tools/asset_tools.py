"""MCP tools over app.services.assets -- search_assets, get_schema,
get_owner, check_pii.

Each exposed function here is a thin wrapper: open a session, call the
one service function that already implements this behavior, shape the
result as a JSON-serializable dict (reusing app.api.schemas' Pydantic
models where a matching shape already exists, so there's exactly one
place -- not three, counting the HTTP API and the agent's own tools --
that defines what an "asset summary" or "column" looks like on the
wire), close the session. No query/business logic lives here.

Every tool returns a consistent envelope: a `found: bool` field for
single-entity lookups (asset doesn't exist -> found=False, distinct from
"exists but the specific field is empty" -> found=True with an empty/null
field), or a plain `count` for list/search-shaped results where "not
found" isn't a meaningful distinct state from "zero results".
"""
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.api import schemas
from app.services import assets as assets_service
from mcp_server.db import get_session


def search_assets(
    query: str | None = None,
    domain: str | None = None,
    asset_type: str | None = None,
    tag: str | None = None,
    pii_only: bool = False,
    owner: str | None = None,
) -> dict[str, Any]:
    """Search ContextIQ's data catalog by keyword, domain, asset type, tag,
    PII status, or owning team. All filters are optional and combine with
    AND. Use this to find a dataset's id, or to answer broad questions
    like "which datasets contain PII" or "which datasets does <team> own"."""
    with get_session() as db:
        results = assets_service.search_assets(
            db, query=query, domain=domain,
            asset_type=asset_type, tag=tag, pii_only=pii_only, owner=owner, limit=50,
        )
        assets = [schemas.AssetSummaryOut.model_validate(a).model_dump(mode="json") for a in results]
        return {"count": len(assets), "assets": assets}


def get_schema(asset_id: str) -> dict[str, Any]:
    """Get the column-level schema for a specific dataset."""
    with get_session() as db:
        columns = assets_service.get_schema(db, asset_id)
        if columns is None:
            return {"found": False, "asset_id": asset_id, "columns": []}
        dumped = [schemas.ColumnOut.model_validate(c).model_dump(mode="json") for c in columns]
        return {"found": True, "asset_id": asset_id, "columns": dumped}


def get_owner(asset_id: str) -> dict[str, Any]:
    """Get the owning team/person for a specific dataset."""
    with get_session() as db:
        asset = assets_service.get_asset(db, asset_id)
        if asset is None:
            return {"found": False, "asset_id": asset_id, "owner": None}
        owner = schemas.OwnerOut.model_validate(asset.owner).model_dump(mode="json") if asset.owner else None
        return {"found": True, "asset_id": asset_id, "owner": owner}


def check_pii(asset_id: str | None = None) -> dict[str, Any]:
    """Check PII status for a specific dataset (asset_id given), or list
    every dataset in the catalog that contains PII (asset_id omitted)."""
    with get_session() as db:
        if asset_id:
            asset = assets_service.get_asset(db, asset_id)
            if asset is None:
                return {"found": False, "asset_id": asset_id, "pii_status": None, "pii_columns": []}
            columns = assets_service.get_schema(db, asset_id) or []
            pii_columns = [
                {"column_name": c.column_name, "pii_category": c.pii_category}
                for c in columns if c.is_pii
            ]
            return {
                "found": True,
                "asset_id": asset_id,
                "pii_status": asset.pii_status.value,
                "pii_columns": pii_columns,
            }

        results = assets_service.search_assets(db, pii_only=True, limit=100)
        return {
            "count": len(results),
            "assets_with_pii": [{"asset_id": a.asset_id, "asset_name": a.asset_name} for a in results],
        }


def register(mcp: FastMCP) -> None:
    mcp.tool()(search_assets)
    mcp.tool()(get_schema)
    mcp.tool()(get_owner)
    mcp.tool()(check_pii)
