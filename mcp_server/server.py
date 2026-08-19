"""
ContextIQ MCP server entrypoint.

A thin adapter over the SAME app.services.* functions the FastAPI backend
and the LangGraph agent already use -- no new business logic, just
another interface. It is a SIBLING to the agent, not a layer it calls
through:

    Agent (app/agent/tools.py)   -->  app/services/*  <--  MCP tools (here)

The agent never calls MCP, and MCP never calls the agent -- both consume
the same service layer independently. See docs/architecture.md and
docs/mcp.md for the full design.

One server implementation, transport chosen at launch (not two
implementations to keep in sync):

    python mcp_server/server.py                       # stdio (default) --
                                                        # for local clients
                                                        # like Claude Desktop
    python mcp_server/server.py --transport streamable-http
                                                        # for Docker / remote
                                                        # access (Phase 14.2)

Transport can also be set via the MCP_TRANSPORT env var (CLI flag wins if
both are given); host/port for the HTTP case via MCP_HOST/MCP_PORT.
"""
import argparse
import os

from mcp.server.fastmcp import FastMCP

import mcp_server  # noqa: F401  -- sys.path bootstrap (backend/ importable)
from mcp_server.tools import register_all

mcp = FastMCP(
    "ContextIQ",
    instructions=(
        "Read-only access to ContextIQ's enterprise data catalog: asset search, "
        "schema, ownership, PII status, lineage, data quality, business term "
        "definitions, and documentation search. Backed by the same service layer "
        "as the ContextIQ chat agent and HTTP API -- every answer traces back to "
        "real catalog rows, never invented."
    ),
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)
register_all(mcp)


def main() -> None:
    parser = argparse.ArgumentParser(description="ContextIQ MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport to serve over (default: stdio, or $MCP_TRANSPORT).",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
