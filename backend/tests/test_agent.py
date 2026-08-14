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
from app.agent.run import NOT_FOUND_MESSAGE, run_agent


def _asset_ids(result) -> set[str]:
    return {e.asset_id for e in result.evidence if e.asset_id}


def _tools_called(result) -> set[str]:
    return {t.tool for t in result.trace}


def test_single_tool_owner_question():
    result = run_agent("Who owns the orders dataset?")
    # search_assets embeds owner inline, so a decisive model can answer
    # correctly from that alone without a separate get_owner call -- both
    # are valid single-tool paths to the same grounded answer, and which
    # one the model picks isn't itself a correctness requirement.
    assert _tools_called(result) & {"get_owner", "search_assets"}
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


# ---------------------------------------------------------------------------
# Multi-hop lineage fix + grounded abstention
#
# See docs/agent.md for the root-cause writeup of the force_answer/
# MAX_ITERATIONS bug this section regression-tests, and for the grounded-
# abstention rules added to SYSTEM_PROMPT.
# ---------------------------------------------------------------------------

def test_multi_hop_lineage_question():
    """Regression test for the force_answer bug: this question needs up to
    4 sequential tool calls (2x search_assets + get_lineage) and used to
    produce an ungrounded "no evidence available" answer once the old
    MAX_ITERATIONS=3 cap was hit mid-chain -- despite real lineage evidence
    for exactly this chain having already been retrieved from Postgres."""
    result = run_agent("Show the lineage from customers to the revenue dashboard.")
    assert "get_lineage" in _tools_called(result)
    assert result.evidence
    ids = _asset_ids(result)
    # Real edges from data/lineage/lineage.yaml: customers -> orders ->
    # order_items -> revenue_model -> monthly_revenue -> revenue_dashboard.
    assert {"order_items", "revenue_model", "monthly_revenue"} & ids
    lowered = result.answer.lower()
    assert "no evidence" not in lowered
    assert "unable to gather" not in lowered


def test_lineage_question_still_works():
    """Regression guard: the existing (single-hop) Phase 6 lineage question
    must keep passing after the MAX_ITERATIONS/force_answer change."""
    result = run_agent("Where does the revenue dashboard's data come from?")
    assert "get_lineage" in _tools_called(result)
    ids = _asset_ids(result)
    assert {"monthly_revenue", "revenue_model"} & ids


def test_unknown_dataset_abstains():
    result = run_agent("What is the owner of the employee_attrition dataset?")
    lowered = result.answer.lower()
    assert "sales engineering" not in lowered  # must not borrow a real owner
    assert any(
        w in lowered
        for w in ["don't have enough information", "could not find", "does not exist", "doesn't exist"]
    )


def test_unknown_business_metric_abstains():
    result = run_agent("What is the company's employee attrition rate?")
    # If the agent's own exploration genuinely turns up nothing, run.py's
    # hard zero-evidence guardrail applies verbatim; if a tangential tool
    # call happened to return unrelated evidence, the model must still
    # abstain on the actual question rather than inventing a number.
    if not result.evidence:
        assert result.answer == NOT_FOUND_MESSAGE
    else:
        lowered = result.answer.lower()
        assert not any(ch.isdigit() for ch in lowered)  # no invented attrition figure
        assert any(w in lowered for w in ["could not find", "don't have enough information", "no ", "not available"])


def test_out_of_domain_question_abstains():
    result = run_agent("What is the weather in Mumbai?")
    if not result.evidence:
        assert result.answer == NOT_FOUND_MESSAGE
    else:
        lowered = result.answer.lower()
        assert not any(w in lowered for w in ["degrees", "celsius", "fahrenheit", "sunny", "rain", "humidity"])
        assert any(w in lowered for w in ["could not find", "don't have enough information", "not available"])


def test_unknown_documentation_abstains():
    result = run_agent(
        "What is ContextIQ's disaster recovery and backup retention policy for the payments database?"
    )
    if not result.evidence:
        assert result.answer == NOT_FOUND_MESSAGE
    else:
        lowered = result.answer.lower()
        # The real gap must be named, not papered over with an invented policy.
        assert any(w in lowered for w in ["no documentation", "does not have", "doesn't have", "could not find", "not available", "no specific"])


def test_partial_evidence_separates_known_from_unavailable():
    result = run_agent(
        "What is the owner of the orders dataset, and what is its GDPR data retention period?"
    )
    # Same search_assets-vs-get_owner tool-choice equivalence as
    # test_single_tool_owner_question above.
    assert _tools_called(result) & {"get_owner", "search_assets"}
    assert "orders" in _asset_ids(result)
    lowered = result.answer.lower()
    assert "sales engineering" in lowered  # the known part is answered
    assert "gdpr" in lowered or "retention" in lowered  # the gap is named, not silently dropped
    assert any(
        w in lowered
        for w in ["no documentation", "not available", "cannot", "couldn't", "could not", "don't have"]
    )
