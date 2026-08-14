"""Integration tests for the ContextIQ agent (Phase 6).

These exercise the FULL agent -- real Ollama LLM (qwen3:4b) tool-calling,
real Postgres (Phase 2/3 catalog + Phase 5 RAG index). Nothing is mocked.
Each run takes tens of seconds to a couple of minutes on CPU-only local
inference, so this suite is slow (several minutes total) by design --
that's the cost of testing the real reasoning path instead of a stub.

Requires: the `db` docker-compose service running and seeded
(scripts/seed_database.py, scripts/ingest_documents.py), and Ollama
running locally with qwen3:4b pulled (`ollama pull qwen3:4b`).

Run with:
    cd backend && ..\\.venv\\Scripts\\pytest tests/test_agent.py -v -s
"""
from app.agent.run import run_agent


def _asset_ids(result) -> set[str]:
    return {e.asset_id for e in result.evidence if e.asset_id}


def _tools_called(result) -> set[str]:
    return {t.tool for t in result.trace}


def test_single_tool_owner_question():
    result = run_agent("Who owns the orders dataset?")
    assert "get_owner" in _tools_called(result)
    assert "orders" in _asset_ids(result)
    assert "sales engineering" in result.answer.lower()


def test_single_tool_business_definition():
    result = run_agent("What does customer lifetime value mean?")
    assert "get_business_definition" in _tools_called(result)
    assert result.evidence
    assert "revenue" in result.answer.lower()


def test_pii_question():
    result = run_agent("Which datasets contain PII?")
    assert _tools_called(result) & {"check_pii", "search_assets"}
    ids = _asset_ids(result)
    assert {"customers", "orders", "payments"} <= ids


def test_lineage_question():
    result = run_agent("Where does the revenue dashboard's data come from?")
    assert "get_lineage" in _tools_called(result)
    ids = _asset_ids(result)
    assert {"monthly_revenue", "revenue_model"} & ids


def test_quality_trust_question():
    result = run_agent("Is the payments dataset trustworthy?")
    assert "check_quality" in _tools_called(result)
    assert "payments" in _asset_ids(result)
    lowered = result.answer.lower()
    assert any(w in lowered for w in ["fail", "not trustworthy", "issue", "freshness", "caution", "concern", "untrustworthy"])


def test_multi_tool_quality_and_lineage():
    result = run_agent("Is the revenue dashboard trustworthy and where does its data come from?")
    called = _tools_called(result)
    assert "check_quality" in called
    assert "get_lineage" in called
    assert len(result.trace) >= 2


def test_multi_tool_pii_and_owner():
    result = run_agent("Which PII datasets are owned by the Sales Engineering team?")
    assert _tools_called(result)
    ids = _asset_ids(result)
    assert ids
    # Sales Engineering owns customers + orders, both of which contain PII.
    assert ids & {"customers", "orders"}


def test_unanswerable_question():
    result = run_agent("What is the capital of France?")
    assert result.evidence == []
    assert "could not find" in result.answer.lower()


def test_no_thinking_leakage_in_answer():
    result = run_agent("Who owns the customers dataset?")
    assert "<think>" not in result.answer.lower()
    assert "</think>" not in result.answer.lower()
