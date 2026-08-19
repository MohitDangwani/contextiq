"""MCP tool over app.services.quality -- check_quality."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.api import schemas
from app.services import quality as quality_service
from mcp_server.db import get_session


def check_quality(asset_id: str) -> dict[str, Any]:
    """Get recorded data quality checks and an overall trust verdict
    (pass/warn/fail) for a dataset. Use this for "is X trustworthy"
    questions."""
    with get_session() as db:
        result = quality_service.check_data_quality(db, asset_id)
        if result is None:
            return {"found": False, "asset_id": asset_id, "quality_score": None, "overall_status": None, "checks": []}
        dumped = schemas.QualityReportOut.model_validate(result).model_dump(mode="json")
        return {"found": True, **dumped}


def register(mcp: FastMCP) -> None:
    mcp.tool()(check_quality)
