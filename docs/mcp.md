# MCP

## What this is

An MCP (Model Context Protocol) server exposing ContextIQ's catalog
capabilities to any MCP-compatible client (Claude Desktop, or any other
MCP host) — independent of the chat agent. Same read-only capabilities
the LangGraph agent has, reachable directly by a client that isn't going
through ContextIQ's own chat UI at all.

## Architecture: a sibling, not a layer

```
Agent (app/agent/tools.py)  ---\
                                 >---  app/services/*  (single source of truth)
MCP client -> mcp_server -------/
```

The agent never calls MCP, and MCP never calls the agent. Both are thin,
independent adapters over the exact same `app/services/*` functions the
FastAPI backend also uses (Phase 4). This is deliberate: `docs/architecture.md`
calls this out as the reason MCP doesn't duplicate any query/business
logic — there is exactly one place that knows how to, say, fetch an
asset's owner, and three thin interfaces on top of it (HTTP API, agent
tool, MCP tool), not three implementations of "fetch an asset's owner."

## The 8 tools

Exactly the same 8 capabilities the agent's tools expose — no more, no
fewer, per the original design ("no new business logic, just another
interface"):

| MCP tool | Wraps | Not found behavior |
|---|---|---|
| `search_assets` | `services.assets.search_assets` | `count: 0, assets: []` (search has no "not found" state, only empty results) |
| `get_schema` | `services.assets.get_schema` | `found: false` |
| `get_owner` | `services.assets.get_asset` | `found: false` if the asset doesn't exist; `found: true, owner: null` if it exists but has no recorded owner — these are different facts, kept distinguishable |
| `check_pii` | `services.assets.get_asset` + `get_schema`, or `search_assets(pii_only=True)` catalog-wide | same `found` distinction as `get_owner` for the single-asset form |
| `get_lineage` | `services.lineage.get_lineage` | `found: false` |
| `check_quality` | `services.quality.check_data_quality` | `found: false` |
| `get_business_definition` | `services.business_terms.get_business_definition` (+ fuzzy fallback) | `found: false` |
| `search_documentation` | `rag.retrieval.semantic_search` | `count: 0, results: []` |

Every tool returns a plain JSON-serializable dict — reusing the same
Pydantic response shapes `app/api/schemas.py` already defines for the
HTTP API wherever the shape matches (`AssetSummaryOut`, `ColumnOut`,
`OwnerOut`, `LineageOut`/`LineageHopOut` — including `via_asset_id`,
Phase 12 — `QualityReportOut`, `BusinessTermOut`), so there's one
definition of what an "asset summary" or "column" looks like on the
wire, not a second one invented for MCP.

**Not exposed, and never will be by design:** `run_sql` (Phase 13). MCP
is a read-only catalog-metadata interface; raw operational-data SQL
access, if built, stays scoped to the agent's own tool surface with its
own explicit gating — see `docs/agent.md`'s security section.

## Running it

```bash
# stdio -- for local MCP clients (e.g. Claude Desktop), from the repo root:
.venv/Scripts/python.exe mcp_server/server.py

# streamable-http -- for remote/Docker access (Phase 14.2):
.venv/Scripts/python.exe mcp_server/server.py --transport streamable-http
# or: MCP_TRANSPORT=streamable-http .venv/Scripts/python.exe mcp_server/server.py
```

One server implementation (`mcp_server/server.py`) — transport is chosen
at launch, not two separate servers to keep in sync. `MCP_HOST`/`MCP_PORT`
env vars configure the HTTP case (defaults `127.0.0.1:8000`; Docker sets
`MCP_HOST=0.0.0.0`, Phase 14.2).

Requires Postgres running and seeded (same as the backend/agent):
`docker start contextiq-db-1` (or `docker compose up -d db`), then
`python scripts/seed_database.py && python scripts/ingest_documents.py`
if not already done.

### Connecting Claude Desktop (stdio)

Add to Claude Desktop's MCP server config:
```json
{
  "mcpServers": {
    "contextiq": {
      "command": "C:\\path\\to\\contextiq\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\contextiq\\mcp_server\\server.py"]
    }
  }
}
```

## Why `mcp_server/` is a sibling of `backend/`, not nested inside it

Matches `docs/architecture.md`'s repository layout (`mcp_server/` and
`backend/` are peers under the repo root). Since `app.services.*` lives
inside `backend/app`, `mcp_server/__init__.py` puts `backend/` on
`sys.path` before anything else in the package imports `app.*` — the
only piece of plumbing needed to make "reuse the same services, don't
duplicate them" actually work across two independently-runnable
processes.

## Tests

`mcp_server/tests/test_mcp_tools.py` (run from the repo root:
`.venv/Scripts/python.exe -m pytest mcp_server/tests/ -v`) — same
"call the underlying function directly against live Postgres, no
LLM/network" pattern as `backend/tests/test_agent_tools.py` (Phase 8),
for all 8 tools: structured output shape, not-found behavior, and the
`found`/`count` distinction above. Plus two protocol-level tests using
an in-process MCP client/server session (`mcp.shared.memory`) confirming
`tools/list` returns exactly the intended 8 (and never `run_sql`), and
that a real `tools/call` round-trips structured content correctly.
