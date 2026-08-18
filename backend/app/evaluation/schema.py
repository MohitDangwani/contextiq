"""Shared data types for the Phase 10 evaluation harness.

Kept separate from app.agent.state on purpose: these describe the
*evaluation* of an agent run (expected vs. actual, scores, aggregates),
not the agent's own execution state. The harness reads an AgentResult
(app.agent.state) as input but never depends on agent internals beyond
that public return type.
"""
from dataclasses import dataclass, field


@dataclass
class BenchmarkQuestion:
    id: str
    category: str
    question: str
    expected_answer: str
    expected_evidence_asset_ids: list[str]
    expected_tools_any_of: list[str]
    should_abstain: bool


@dataclass
class DeterministicMetrics:
    """Metrics computable with no LLM call -- fast, free, and perfectly
    reproducible for the same agent output. `None` on a field means "not
    applicable to this question" (e.g. tool_choice_correct is meaningless
    for a business-definition question with no asset evidence), and such
    fields are excluded from aggregate averages, not counted as failures.
    """

    tool_choice_correct: bool | None
    evidence_overlap: float | None  # fraction of expected_evidence_asset_ids actually present
    abstention_correct: bool
    keyword_hit: float  # fraction of expected_answer's significant words found in the actual answer
    think_leak: bool
    latency_s: float


@dataclass
class JudgeScore:
    score: int | None  # 0, 1, or 2; None if the judge response couldn't be parsed
    reasoning: str


@dataclass
class QuestionResult:
    question: BenchmarkQuestion
    answer: str
    tools_called: list[str]
    evidence_asset_ids: list[str]
    deterministic: DeterministicMetrics
    correctness: JudgeScore | None  # None when --judge wasn't passed
    groundedness: JudgeScore | None


@dataclass
class EvaluationSummary:
    results: list[QuestionResult] = field(default_factory=list)
    total_runtime_s: float = 0.0

    @property
    def n(self) -> int:
        return len(self.results)

    @property
    def avg_latency_s(self) -> float:
        return sum(r.deterministic.latency_s for r in self.results) / self.n if self.n else 0.0

    @property
    def tool_choice_accuracy(self) -> float | None:
        applicable = [r.deterministic.tool_choice_correct for r in self.results
                      if r.deterministic.tool_choice_correct is not None]
        return sum(applicable) / len(applicable) if applicable else None

    @property
    def evidence_overlap_avg(self) -> float | None:
        applicable = [r.deterministic.evidence_overlap for r in self.results
                      if r.deterministic.evidence_overlap is not None]
        return sum(applicable) / len(applicable) if applicable else None

    @property
    def abstention_accuracy(self) -> float:
        return sum(r.deterministic.abstention_correct for r in self.results) / self.n if self.n else 0.0

    @property
    def keyword_hit_avg(self) -> float:
        return sum(r.deterministic.keyword_hit for r in self.results) / self.n if self.n else 0.0

    @property
    def think_leak_count(self) -> int:
        return sum(1 for r in self.results if r.deterministic.think_leak)

    @property
    def judge_used(self) -> bool:
        return any(r.correctness is not None for r in self.results)

    @property
    def avg_correctness(self) -> float | None:
        scores = [r.correctness.score for r in self.results if r.correctness and r.correctness.score is not None]
        return sum(scores) / len(scores) if scores else None

    @property
    def avg_groundedness(self) -> float | None:
        scores = [r.groundedness.score for r in self.results if r.groundedness and r.groundedness.score is not None]
        return sum(scores) / len(scores) if scores else None
