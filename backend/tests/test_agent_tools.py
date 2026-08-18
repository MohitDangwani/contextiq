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

from app.agent.graph import _looks_incomplete
from app.agent.text import extract_json_object
from app.agent.tools import AssetIdArgs, _sanitize_args, build_tool_specs
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


def test_get_lineage_hop_states_its_own_direct_edge(specs):
    """Regression for a lineage relationship-type mixup: a multi-hop query
    used to return each hop as just "N hops away via TRANSFORMATION" with
    no stated endpoints, leaving an LLM narrating the chain free to
    misattribute one edge's transformation to an adjacent edge. Every
    hop's evidence must now name its OWN specific two endpoints, so a
    transformation can never be read as belonging to the wrong edge --
    checked generically across two different hops in the same query, not
    tied to one benchmark question."""
    result = specs["get_lineage"].run(asset_id="revenue_dashboard", direction="upstream")
    by_id = {e.asset_id: e.detail for e in result.evidence}

    # orders -> order_items is a foreign key, NOT the dbt model that
    # connects order_items -> revenue_model one hop further out.
    assert "orders -> order_items" in by_id["orders"]
    assert "foreign key" in by_id["orders"].lower()
    assert "revenue_model" not in by_id["orders"]

    # order_items -> revenue_model is the dbt model -- its own, distinct edge.
    assert "order_items -> revenue_model" in by_id["order_items"]
    assert "dbt model" in by_id["order_items"].lower()


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


# ---------------------------------------------------------------------------
# Class 16: malformed optional tool arguments (the literal-"None" bug)
# ---------------------------------------------------------------------------

def test_sanitize_args_coerces_literal_none_string():
    assert _sanitize_args({"asset_id": "None", "query": "orders"}) == {"asset_id": None, "query": "orders"}


def test_sanitize_args_coerces_null_case_insensitive():
    assert _sanitize_args({"owner": "NULL", "domain": "  none  "}) == {"owner": None, "domain": None}


def test_sanitize_args_leaves_real_values_and_types_alone():
    assert _sanitize_args({"pii_only": True, "query": "revenue", "owner": None}) == {
        "pii_only": True, "query": "revenue", "owner": None,
    }


# ---------------------------------------------------------------------------
# Class 15: empty/stub model response detection
# ---------------------------------------------------------------------------

def test_looks_incomplete_empty_content():
    assert _looks_incomplete("") is True
    assert _looks_incomplete(None) is True


def test_looks_incomplete_stub_header():
    assert _looks_incomplete("Final Answer:") is True


def test_looks_incomplete_give_up_only_when_evidence_exists():
    assert _looks_incomplete("Unable to determine.", has_evidence=True) is True
    # Without evidence, this isn't a "gave up despite having it" case --
    # run.py's zero-evidence backstop is what handles that path.
    assert _looks_incomplete("Unable to determine.", has_evidence=False) is False


def test_looks_incomplete_real_answer_is_not_flagged():
    assert _looks_incomplete("The orders dataset is owned by Sales Engineering.", has_evidence=True) is False


# ---------------------------------------------------------------------------
# Shared JSON-verdict parsing (used by the Phase 10 judge and the
# grounding verifier)
# ---------------------------------------------------------------------------

def test_extract_json_object_clean():
    assert extract_json_object('{"status": "supported", "reasoning": "ok"}') == {
        "status": "supported", "reasoning": "ok",
    }


def test_extract_json_object_wrapped_in_extra_text():
    parsed = extract_json_object('Sure, here you go:\n{"score": 1, "reasoning": "partial"}\nDone.')
    assert parsed == {"score": 1, "reasoning": "partial"}


def test_extract_json_object_malformed_returns_none():
    assert extract_json_object("I think this is good, no JSON here") is None
    assert extract_json_object("") is None
    assert extract_json_object(None) is None
