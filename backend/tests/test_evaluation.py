"""Unit tests for the Phase 10 evaluation harness itself -- deterministic
metrics, the benchmark loader, and judge response parsing. No LLM, no DB:
these test the harness's own logic against synthetic AgentResult objects,
the same way test_agent_tools.py tests tool logic directly rather than
through a live model. The harness's behavior against the REAL agent is
what `python scripts/run_evaluation.py` itself verifies -- that's an
integration run, not something to fake here.
"""
from app.agent.state import AgentResult, EvidenceItem, SourceRef, ToolInvocation
from app.evaluation.benchmark import load_benchmark
from app.evaluation.deterministic import compute_deterministic_metrics, is_abstention
from app.evaluation.judge import _parse_judge_response
from app.evaluation.schema import BenchmarkQuestion, DeterministicMetrics, JudgeScore, QuestionResult


def _result(answer: str, tools: list[str] = (), asset_ids: list[str] = ()) -> AgentResult:
    evidence = [
        EvidenceItem(source_type="asset", title=a, asset_id=a, detail=f"{a} detail", citation=f"{a} cite")
        for a in asset_ids
    ]
    trace = [ToolInvocation(tool=t, input={}, output_summary="ok", timestamp="2026-01-01T00:00:00Z") for t in tools]
    return AgentResult(question="q", answer=answer, sources=[], evidence=evidence, trace=trace)


def _question(**overrides) -> BenchmarkQuestion:
    base = dict(
        id="qX", category="known_factual", question="Who owns X?",
        expected_answer="X is owned by Sales Engineering.",
        expected_evidence_asset_ids=["x"], expected_tools_any_of=["get_owner", "search_assets"],
        should_abstain=False,
    )
    base.update(overrides)
    return BenchmarkQuestion(**base)


# --- benchmark loader ---------------------------------------------------

def test_benchmark_loads_30_questions():
    questions = load_benchmark()
    assert len(questions) == 30
    assert len({q.id for q in questions}) == 30  # all ids unique


def test_benchmark_limit():
    questions = load_benchmark(limit=8)
    assert len(questions) == 8


def test_benchmark_covers_expected_categories():
    questions = load_benchmark()
    categories = {q.category for q in questions}
    for expected in ["known_factual", "multi_tool", "lineage", "quality", "pii", "business_definition"]:
        assert expected in categories
    assert any(c.startswith("abstention") for c in categories)


def test_benchmark_abstention_questions_have_no_expected_evidence():
    for q in load_benchmark():
        if q.should_abstain:
            assert q.expected_evidence_asset_ids == []
            assert q.expected_tools_any_of == []


# --- deterministic metrics -----------------------------------------------

def test_is_abstention_detects_hard_backstop_message():
    from app.agent.run import NOT_FOUND_MESSAGE
    assert is_abstention(NOT_FOUND_MESSAGE)


def test_is_abstention_false_for_real_answer():
    assert not is_abstention("The orders dataset is owned by Sales Engineering.")


def test_deterministic_metrics_correct_answer():
    q = _question()
    result = _result("X is owned by Sales Engineering.", tools=["get_owner"], asset_ids=["x"])
    det = compute_deterministic_metrics(q, result, latency_s=1.5)
    assert det.tool_choice_correct is True
    assert det.evidence_overlap == 1.0
    assert det.abstention_correct is True  # correctly did NOT abstain
    assert det.keyword_hit > 0.5
    assert det.think_leak is False
    assert det.latency_s == 1.5


def test_deterministic_metrics_wrong_tool():
    q = _question()
    result = _result("X is owned by Sales Engineering.", tools=["get_lineage"], asset_ids=["x"])
    det = compute_deterministic_metrics(q, result, latency_s=1.0)
    assert det.tool_choice_correct is False


def test_deterministic_metrics_partial_evidence():
    q = _question(expected_evidence_asset_ids=["x", "y"])
    result = _result("X is owned by Sales Engineering.", tools=["get_owner"], asset_ids=["x"])
    det = compute_deterministic_metrics(q, result, latency_s=1.0)
    assert det.evidence_overlap == 0.5


def test_deterministic_metrics_abstention_question_correctly_abstained():
    q = _question(should_abstain=True, expected_evidence_asset_ids=[], expected_tools_any_of=[])
    from app.agent.run import NOT_FOUND_MESSAGE
    result = _result(NOT_FOUND_MESSAGE)
    det = compute_deterministic_metrics(q, result, latency_s=0.5)
    assert det.abstention_correct is True
    assert det.tool_choice_correct is None  # not scored for abstention questions


def test_deterministic_metrics_abstention_question_hallucinated_instead():
    q = _question(should_abstain=True, expected_evidence_asset_ids=[], expected_tools_any_of=[])
    result = _result("X is owned by Sales Engineering.")  # should have abstained but didn't
    det = compute_deterministic_metrics(q, result, latency_s=0.5)
    assert det.abstention_correct is False


def test_deterministic_metrics_think_leak_detected():
    q = _question()
    result = _result("<think>reasoning</think>X is owned by Sales Engineering.", tools=["get_owner"], asset_ids=["x"])
    det = compute_deterministic_metrics(q, result, latency_s=1.0)
    assert det.think_leak is True


# --- judge response parsing ----------------------------------------------

def test_parse_judge_response_clean_json():
    score = _parse_judge_response('{"score": 2, "reasoning": "matches the reference"}')
    assert score.score == 2
    assert "matches" in score.reasoning


def test_parse_judge_response_json_wrapped_in_extra_text():
    score = _parse_judge_response('Sure, here is my answer:\n{"score": 1, "reasoning": "partially right"}\nDone.')
    assert score.score == 1


def test_parse_judge_response_malformed_falls_back_gracefully():
    score = _parse_judge_response("I think this is pretty good, no JSON here")
    assert score.score is None
    assert "unparseable" in score.reasoning


def test_parse_judge_response_out_of_range_score():
    score = _parse_judge_response('{"score": 5, "reasoning": "too high"}')
    assert score.score is None
