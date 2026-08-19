"""MCP tool over app.services.business_terms -- get_business_definition."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.api import schemas
from app.services import business_terms as business_term_service
from mcp_server.db import get_session


def get_business_definition(term: str) -> dict[str, Any]:
    """Look up the definition of a business term or metric, e.g.
    'customer lifetime value'. Falls back to a fuzzy keyword match if
    there's no exact match on the term name."""
    with get_session() as db:
        result = business_term_service.get_business_definition(db, term.strip().replace(" ", "_"))
        if result is None:
            candidates = business_term_service.search_business_terms(db, term, limit=1)
            result = candidates[0] if candidates else None
        if result is None:
            return {"found": False, "term": term, "definition": None, "domain": None}
        dumped = schemas.BusinessTermOut.model_validate(result).model_dump(mode="json")
        return {"found": True, **dumped}


def register(mcp: FastMCP) -> None:
    mcp.tool()(get_business_definition)
