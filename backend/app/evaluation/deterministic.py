"""Deterministic (no-LLM-call) evaluation metrics.

These are fast, free, and perfectly reproducible for the same agent
output -- unlike the LLM judge, running this twice on the same
QuestionResult always gives the same numbers. They're a floor, not a
replacement for the judge: a keyword overlap or an asset-id match is a
weak proxy for "the answer is actually correct", which is exactly why
the LLM judge exists as a second, semantic layer (see judge.py).
"""
import re

from app.agent.run import NOT_FOUND_MESSAGE
from app.agent.state import AgentResult
from app.agent.text import flags_gap
from app.evaluation.schema import BenchmarkQuestion, DeterministicMetrics

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "and", "or", "of", "to", "in",
    "on", "for", "with", "its", "it", "that", "this", "as", "by", "from", "be",
    "not", "no", "over", "their", "which", "does", "do", "what",
}


def is_abstention(answer: str) -> bool:
    """Whether a full answer is a (or reduces to a) real abstention.
    Matching run.py's NOT_FOUND_MESSAGE exactly is the strong signal;
    flags_gap (app/agent/text.py) is the shared fallback for an
    abstention phrased differently -- kept in one place so this and
    backend/tests/test_agent.py agree on what "abstained" means."""
    return answer.strip() == NOT_FOUND_MESSAGE or flags_gap(answer)


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _keyword_hit(expected_answer: str, actual_answer: str) -> float:
    expected_words = _significant_words(expected_answer)
    if not expected_words:
        return 1.0
    lowered_actual = actual_answer.lower()
    hits = sum(1 for w in expected_words if w in lowered_actual)
    return hits / len(expected_words)


def compute_deterministic_metrics(
    question: BenchmarkQuestion, result: AgentResult, latency_s: float
) -> DeterministicMetrics:
    tools_called = {t.tool for t in result.trace}
    evidence_ids = {e.asset_id for e in result.evidence if e.asset_id}
    abstained = is_abstention(result.answer)

    if question.should_abstain:
        tool_choice_correct = None  # any exploratory tools are fine as long as it still abstains
        evidence_overlap = None
    elif question.expected_tools_any_of:
        tool_choice_correct = bool(tools_called & set(question.expected_tools_any_of))
        evidence_overlap = None
        if question.expected_evidence_asset_ids:
            expected = set(question.expected_evidence_asset_ids)
            evidence_overlap = len(evidence_ids & expected) / len(expected)
    else:
        tool_choice_correct = None
        evidence_overlap = None

    abstention_correct = abstained if question.should_abstain else not abstained

    return DeterministicMetrics(
        tool_choice_correct=tool_choice_correct,
        evidence_overlap=evidence_overlap,
        abstention_correct=abstention_correct,
        keyword_hit=_keyword_hit(question.expected_answer, result.answer),
        think_leak=("<think>" in result.answer.lower() or "</think>" in result.answer.lower()),
        latency_s=latency_s,
    )
