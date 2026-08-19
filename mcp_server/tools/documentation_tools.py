"""MCP tool over app.rag.retrieval.semantic_search -- search_documentation.

Same DOC_SIMILARITY_THRESHOLD noise filter app/agent/tools.py uses, kept
as a local constant rather than imported from there since that module is
agent-specific (imports langchain_core) and importing it here would pull
LangGraph/LangChain into the MCP process for no reason -- the threshold
value itself is the only thing worth sharing, and it's a single float.
"""
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.rag.retrieval import semantic_search
from mcp_server.db import get_session

DOC_SIMILARITY_THRESHOLD = 0.35


def search_documentation(query: str, asset_id: str | None = None) -> dict[str, Any]:
    """Semantic search over ContextIQ's documentation and policies, for
    free-text questions not covered by the other tools (e.g. general
    policies, dashboard descriptions, refresh schedules)."""
    with get_session() as db:
        hits = semantic_search(db, query, k=5, asset_id=asset_id)
        hits = [h for h in hits if h.similarity >= DOC_SIMILARITY_THRESHOLD]
        results = [
            {
                "title": h.title,
                "content": h.content,
                "source_type": h.source_type,
                "asset_id": h.asset_id,
                "source_url": h.source_url,
                "similarity": round(h.similarity, 4),
            }
            for h in hits
        ]
        return {"count": len(results), "results": results}


def register(mcp: FastMCP) -> None:
    mcp.tool()(search_documentation)
