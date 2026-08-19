"""Independent MCP tool-layer tests (Phase 9), same spirit and same live
seed data as backend/tests/test_agent_tools.py (Phase 8) -- these call
each MCP tool's underlying function directly against live Postgres, no
protocol/transport involved, covering structured output and not-found
behavior for all 8 tools. A separate protocol-level test at the bottom
confirms the actual MCP tools/list surface matches exactly these 8.

Requires: the `db` docker-compose service running and seeded
(scripts/seed_database.py, scripts/ingest_documents.py).
"""
import pytest

from mcp_server.tools.asset_tools import check_pii, get_owner, get_schema, search_assets
from mcp_server.tools.business_term_tools import get_business_definition
from mcp_server.tools.documentation_tools import search_documentation
from mcp_server.tools.lineage_tools import get_lineage
from mcp_server.tools.quality_tools import check_quality

# ---------------------------------------------------------------------------
# search_assets
# ---------------------------------------------------------------------------


def test_search_assets_no_filters_returns_all():
    result = search_assets()
    ids = {a["asset_id"] for a in result["assets"]}
    assert {"customers", "orders", "revenue_dashboard"} <= ids
    assert result["count"] == len(result["assets"])


def test_search_assets_pii_only():
    result = search_assets(pii_only=True)
    ids = {a["asset_id"] for a in result["assets"]}
    assert ids == {"customers", "orders", "payments"}


def test_search_assets_pii_and_owner_combined():
    result = search_assets(pii_only=True, owner="Sales Engineering")
    ids = {a["asset_id"] for a in result["assets"]}
    assert ids == {"customers", "orders"}


def test_search_assets_no_match():
    result = search_assets(query="no_such_dataset_xyz")
    assert result == {"count": 0, "assets": []}


# ---------------------------------------------------------------------------
# get_schema
# ---------------------------------------------------------------------------


def test_get_schema_known_asset():
    result = get_schema(asset_id="orders")
    assert result["found"] is True
    columns = {c["column_name"] for c in result["columns"]}
    assert {"order_id", "customer_id", "status"} <= columns


def test_get_schema_asset_with_no_columns():
    result = get_schema(asset_id="revenue_dashboard")
    assert result == {"found": True, "asset_id": "revenue_dashboard", "columns": []}


def test_get_schema_unknown_asset():
    result = get_schema(asset_id="not_a_real_asset")
    assert result == {"found": False, "asset_id": "not_a_real_asset", "columns": []}


# ---------------------------------------------------------------------------
# get_owner
# ---------------------------------------------------------------------------


def test_get_owner_known_asset():
    result = get_owner(asset_id="customers")
    assert result["found"] is True
    assert "sales engineering" in result["owner"]["team"].lower() or "sales engineering" in result["owner"]["name"].lower()


def test_get_owner_unknown_asset():
    result = get_owner(asset_id="not_a_real_asset")
    assert result == {"found": False, "asset_id": "not_a_real_asset", "owner": None}


# ---------------------------------------------------------------------------
# check_pii
# ---------------------------------------------------------------------------


def test_check_pii_asset_with_pii():
    result = check_pii(asset_id="customers")
    assert result["found"] is True
    categories = {c["pii_category"] for c in result["pii_columns"]}
    assert any(cat and "email" in cat for cat in categories)


def test_check_pii_asset_without_pii():
    result = check_pii(asset_id="order_items")
    assert result["found"] is True
    assert result["pii_columns"] == []


def test_check_pii_catalog_wide():
    result = check_pii()
    ids = {a["asset_id"] for a in result["assets_with_pii"]}
    assert ids == {"customers", "orders", "payments"}


def test_check_pii_unknown_asset():
    result = check_pii(asset_id="not_a_real_asset")
    assert result == {"found": False, "asset_id": "not_a_real_asset", "pii_status": None, "pii_columns": []}


# ---------------------------------------------------------------------------
# get_lineage
# ---------------------------------------------------------------------------


def test_get_lineage_downstream():
    result = get_lineage(asset_id="customers", direction="downstream")
    ids = {h["asset_id"] for h in result["downstream"]}
    assert ids == {"orders", "order_items", "revenue_model", "monthly_revenue", "revenue_dashboard"}
    assert result["upstream"] == []


def test_get_lineage_upstream():
    result = get_lineage(asset_id="revenue_dashboard", direction="upstream")
    ids = {h["asset_id"] for h in result["upstream"]}
    assert ids == {
        "monthly_revenue", "revenue_model", "order_items", "payments",
        "returns", "products", "orders", "customers",
    }
    # via_asset_id (Phase 12) should be present on every hop -- this is an
    # MCP client's only way to know a hop's exact edge endpoints.
    assert all(h["via_asset_id"] for h in result["upstream"])


def test_get_lineage_standalone_asset():
    result = get_lineage(asset_id="marketing_campaigns", direction="both")
    assert result == {
        "found": True, "asset_id": "marketing_campaigns", "upstream": [], "downstream": [],
    }


def test_get_lineage_unknown_asset():
    result = get_lineage(asset_id="not_a_real_asset")
    assert result == {"found": False, "asset_id": "not_a_real_asset", "upstream": [], "downstream": []}


# ---------------------------------------------------------------------------
# check_quality
# ---------------------------------------------------------------------------


def test_check_quality_failing_asset():
    result = check_quality(asset_id="payments")
    assert result["overall_status"] == "fail"


def test_check_quality_passing_asset():
    result = check_quality(asset_id="customers")
    assert result["overall_status"] == "pass"


def test_check_quality_unknown_asset():
    result = check_quality(asset_id="not_a_real_asset")
    assert result["found"] is False


# ---------------------------------------------------------------------------
# get_business_definition
# ---------------------------------------------------------------------------


def test_get_business_definition_exact():
    result = get_business_definition(term="customer_lifetime_value")
    assert result["found"] is True
    assert "revenue" in result["definition"].lower()


def test_get_business_definition_fuzzy():
    result = get_business_definition(term="net revenue")
    assert result["found"] is True
    assert "refund" in result["definition"].lower() or "gross" in result["definition"].lower()


def test_get_business_definition_unknown_term():
    result = get_business_definition(term="totally_made_up_term_xyz")
    assert result == {"found": False, "term": "totally_made_up_term_xyz", "definition": None, "domain": None}


# ---------------------------------------------------------------------------
# search_documentation
# ---------------------------------------------------------------------------


def test_search_documentation_relevant_query():
    result = search_documentation(query="which datasets contain personal information")
    assert result["count"] > 0


def test_search_documentation_asset_scoped():
    result = search_documentation(query="refresh schedule", asset_id="revenue_dashboard")
    for r in result["results"]:
        assert r["asset_id"] == "revenue_dashboard"


def test_search_documentation_no_match():
    result = search_documentation(query="xyzzy nonsense query unrelated to anything")
    assert result == {"count": 0, "results": []}


# ---------------------------------------------------------------------------
# Protocol-level: the actual MCP tools/list surface, over a real in-process
# client/server session (not just calling the Python functions directly).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_tools_list_matches_intended_set():
    from mcp.shared.memory import create_connected_server_and_client_session

    from mcp_server.server import mcp as server

    async with create_connected_server_and_client_session(server._mcp_server) as client:
        response = await client.list_tools()
        names = {t.name for t in response.tools}

    assert names == {
        "search_assets", "get_schema", "get_owner", "check_pii",
        "get_lineage", "check_quality", "get_business_definition", "search_documentation",
    }
    # The one capability that must NEVER appear here.
    assert "run_sql" not in names


@pytest.mark.asyncio
async def test_mcp_call_tool_over_protocol_returns_structured_content():
    from mcp.shared.memory import create_connected_server_and_client_session

    from mcp_server.server import mcp as server

    async with create_connected_server_and_client_session(server._mcp_server) as client:
        result = await client.call_tool("get_owner", {"asset_id": "customers"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent.get("found") is True
