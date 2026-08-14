"""Independent tool-layer tests (Phase 8).

Unlike tests/test_agent.py (which drives the full LLM-orchestrated
agent, ~2.7 min/question), these call each tool's underlying `run`
function directly -- no LLM, no Ollama -- against the live Postgres
database. This is what satisfies the "each tool must be independently
testable" requirement: every capability can be verified in isolation,
fast (seconds, not minutes), from input validation through to structured
output and not-found/error handling.

Requires: the `db` docker-compose service running and seeded
(scripts/seed_database.py, scripts/ingest_documents.py).
"""
import pytest
from pydantic import ValidationError

from app.agent.tools import AssetIdArgs, build_tool_specs
from app.config.database import SessionLocal


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def specs(db):
    return build_tool_specs(db)


# ---------------------------------------------------------------------------
# search_assets
# ---------------------------------------------------------------------------

def test_search_assets_no_filters_returns_all(specs):
    result = specs["search_assets"].run()
    ids = {e.asset_id for e in result.evidence}
    assert {"customers", "orders", "revenue_dashboard"} <= ids


def test_search_assets_pii_only(specs):
    result = specs["search_assets"].run(pii_only=True)
    ids = {e.asset_id for e in result.evidence}
    assert ids == {"customers", "orders", "payments"}


def test_search_assets_pii_and_owner_combined(specs):
    result = specs["search_assets"].run(pii_only=True, owner="Sales Engineering")
    ids = {e.asset_id for e in result.evidence}
    assert ids == {"customers", "orders"}


def test_search_assets_no_match(specs):
    result = specs["search_assets"].run(query="no_such_dataset_xyz")
    assert result.evidence == []
    assert "no datasets matched" in result.summary.lower()


# ---------------------------------------------------------------------------
# get_schema
# ---------------------------------------------------------------------------

def test_get_schema_known_asset(specs):
    result = specs["get_schema"].run(asset_id="orders")
    columns = {e.title.split(".")[-1] for e in result.evidence}
    assert {"order_id", "customer_id", "status"} <= columns


def test_get_schema_asset_with_no_columns(specs):
    result = specs["get_schema"].run(asset_id="revenue_dashboard")
    assert result.evidence == []
    assert "no modeled columns" in result.summary.lower()


def test_get_schema_unknown_asset(specs):
    result = specs["get_schema"].run(asset_id="not_a_real_asset")
    assert result.evidence == []
    assert "not_a_real_asset" in result.summary
    assert "orders" in result.summary  # helpful "known ids" hint


# ---------------------------------------------------------------------------
# get_owner
# ---------------------------------------------------------------------------

def test_get_owner_known_asset(specs):
    result = specs["get_owner"].run(asset_id="customers")
    assert "sales engineering" in result.summary.lower()
    assert result.evidence[0].asset_id == "customers"


def test_get_owner_unknown_asset(specs):
    result = specs["get_owner"].run(asset_id="not_a_real_asset")
    assert result.evidence == []


# ---------------------------------------------------------------------------
# check_pii
# ---------------------------------------------------------------------------

def test_check_pii_asset_with_pii(specs):
    result = specs["check_pii"].run(asset_id="customers")
    categories = {e.detail for e in result.evidence}
    assert any("email" in c for c in categories)


def test_check_pii_asset_without_pii(specs):
    result = specs["check_pii"].run(asset_id="order_items")
    assert "does not contain pii" in result.summary.lower()


def test_check_pii_catalog_wide(specs):
    result = specs["check_pii"].run()
    ids = {e.asset_id for e in result.evidence}
    assert ids == {"customers", "orders", "payments"}


def test_check_pii_unknown_asset(specs):
    result = specs["check_pii"].run(asset_id="not_a_real_asset")
    assert result.evidence == []


# ---------------------------------------------------------------------------
# get_lineage
# ---------------------------------------------------------------------------

def test_get_lineage_downstream(specs):
    result = specs["get_lineage"].run(asset_id="customers", direction="downstream")
    ids = {e.asset_id for e in result.evidence}
    assert ids == {"orders", "order_items", "revenue_model", "monthly_revenue", "revenue_dashboard"}


def test_get_lineage_upstream(specs):
    result = specs["get_lineage"].run(asset_id="revenue_dashboard", direction="upstream")
    ids = {e.asset_id for e in result.evidence}
    assert ids == {
        "monthly_revenue", "revenue_model", "order_items", "payments",
        "returns", "products", "orders", "customers",
    }


def test_get_lineage_standalone_asset(specs):
    result = specs["get_lineage"].run(asset_id="marketing_campaigns", direction="both")
    assert result.evidence == []
    assert "no recorded lineage" in result.summary.lower()


def test_get_lineage_unknown_asset(specs):
    result = specs["get_lineage"].run(asset_id="not_a_real_asset")
    assert result.evidence == []


# ---------------------------------------------------------------------------
# check_quality
# ---------------------------------------------------------------------------

def test_check_quality_failing_asset(specs):
    result = specs["check_quality"].run(asset_id="payments")
    assert "fail" in result.summary.lower()


def test_check_quality_passing_asset(specs):
    result = specs["check_quality"].run(asset_id="customers")
    assert "overall: pass" in result.summary.lower()


def test_check_quality_unknown_asset(specs):
    result = specs["check_quality"].run(asset_id="not_a_real_asset")
    assert result.evidence == []


# ---------------------------------------------------------------------------
# get_business_definition
# ---------------------------------------------------------------------------

def test_get_business_definition_exact(specs):
    result = specs["get_business_definition"].run(term="customer_lifetime_value")
    assert "revenue" in result.summary.lower()


def test_get_business_definition_fuzzy(specs):
    result = specs["get_business_definition"].run(term="net revenue")
    assert "refund" in result.summary.lower() or "gross" in result.summary.lower()


def test_get_business_definition_unknown_term(specs):
    result = specs["get_business_definition"].run(term="totally_made_up_term_xyz")
    assert result.evidence == []


# ---------------------------------------------------------------------------
# search_documentation
# ---------------------------------------------------------------------------

def test_search_documentation_relevant_query(specs):
    result = specs["search_documentation"].run(query="which datasets contain personal information")
    assert result.evidence
    assert any(e.source_type == "documentation" for e in result.evidence)


def test_search_documentation_asset_scoped(specs):
    result = specs["search_documentation"].run(query="refresh schedule", asset_id="revenue_dashboard")
    for e in result.evidence:
        assert e.asset_id == "revenue_dashboard"


# ---------------------------------------------------------------------------
# Input validation (the Pydantic args_schema every tool is registered with)
# ---------------------------------------------------------------------------

def test_missing_required_arg_is_rejected():
    with pytest.raises(ValidationError):
        AssetIdArgs()


def test_tool_schema_exposes_name_and_description(specs):
    for name, spec in specs.items():
        assert spec.tool.name == name
        assert spec.tool.description
        assert spec.tool.args_schema is not None
