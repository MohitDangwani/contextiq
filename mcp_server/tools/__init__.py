"""The 8 MCP tools, grouped into modules that mirror app/services/*'s own
module boundaries one-to-one (asset/lineage/quality/business_term/
documentation) -- same shape as app/agent/tools.py's capability list,
registered here instead of bound to an LLM."""
from mcp.server.fastmcp import FastMCP

from . import asset_tools, business_term_tools, documentation_tools, lineage_tools, quality_tools


def register_all(mcp: FastMCP) -> None:
    asset_tools.register(mcp)
    lineage_tools.register(mcp)
    quality_tools.register(mcp)
    business_term_tools.register(mcp)
    documentation_tools.register(mcp)
