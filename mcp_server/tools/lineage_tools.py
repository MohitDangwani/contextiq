"""MCP tool over app.services.lineage -- get_lineage.

Reuses the same LineageOut/LineageHopOut shape the HTTP API already
returns (including via_asset_id, Phase 12) -- one lineage response shape
across the API and MCP, not two.
"""
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.api import schemas
from app.services import lineage as lineage_service
from mcp_server.db import get_session


def get_lineage(asset_id: str, direction: str = "both") -> dict[str, Any]:
    """Get upstream/downstream data lineage for a dataset. direction is
    'upstream' (what feeds into this dataset), 'downstream' (what this
    dataset feeds into), or 'both'."""
    with get_session() as db:
        result = lineage_service.get_lineage(db, asset_id, direction=direction)
        if result is None:
            return {"found": False, "asset_id": asset_id, "upstream": [], "downstream": []}
        dumped = schemas.LineageOut.model_validate(result).model_dump(mode="json")
        return {"found": True, **dumped}


def register(mcp: FastMCP) -> None:
    mcp.tool()(get_lineage)
