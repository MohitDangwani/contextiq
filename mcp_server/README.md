# ContextIQ MCP Server

A thin MCP (Model Context Protocol) adapter over the same
`app/services/*` layer the FastAPI backend and the LangGraph agent use —
see `docs/mcp.md` for the full design, and `docs/architecture.md` for how
this fits into ContextIQ as a whole. Independent of the chat agent: MCP
clients reach ContextIQ's catalog directly, not through the agent.

## Quick start

```bash
# from the repo root, with Postgres running and seeded:
.venv/Scripts/python.exe mcp_server/server.py                              # stdio
.venv/Scripts/python.exe mcp_server/server.py --transport streamable-http  # HTTP
```

## Tools

`search_assets`, `get_schema`, `get_owner`, `check_pii`, `get_lineage`,
`check_quality`, `get_business_definition`, `search_documentation` — the
same 8 capabilities the agent has, nothing more. `run_sql` is
intentionally never exposed here.

## Tests

```bash
# from the repo root:
.venv/Scripts/python.exe -m pytest mcp_server/tests/ -v
```

## Layout

```
mcp_server/
  __init__.py         sys.path bootstrap so app.* (in backend/) is importable
  db.py                one DB session per tool call
  server.py             FastMCP instance, tool registration, transport selection
  tools/
    asset_tools.py       search_assets, get_schema, get_owner, check_pii
    lineage_tools.py      get_lineage
    quality_tools.py      check_quality
    business_term_tools.py  get_business_definition
    documentation_tools.py  search_documentation
  tests/
    test_mcp_tools.py    all 8 tools + protocol-level tools/list smoke test
```
