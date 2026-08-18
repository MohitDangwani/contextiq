"""Evaluation runner: executes the real agent (app.agent.run.run_agent)
against each benchmark question, scores it, and aggregates results.

No mocks: every question is a real LangGraph run against whichever
LLM_PROVIDER is configured (LM Studio/Nemotron or Ollama/Qwen3, unchanged
from app.config.settings) and the real seeded Postgres database. This
file only *observes* app.agent.run.run_agent's output -- it never touches
graph.py, tools.py, or the grounding guardrail in run.py.
"""
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.agent.run import run_agent
from app.evaluation.benchmark import DEFAULT_BENCHMARK_PATH, load_benchmark
from app.evaluation.deterministic import compute_deterministic_metrics
from app.evaluation.judge import judge_correctness, judge_groundedness
from app.evaluation.schema import EvaluationSummary, QuestionResult

RESULTS_DIR = DEFAULT_BENCHMARK_PATH.parent / "results"


def run_evaluation(limit: int | None = None, use_judge: bool = False) -> EvaluationSummary:
    questions = load_benchmark(limit=limit)
    summary = EvaluationSummary()
    run_start = time.monotonic()

    for q in questions:
        q_start = time.monotonic()
        result = run_agent(q.question)
        latency_s = time.monotonic() - q_start

        det = compute_deterministic_metrics(q, result, latency_s)
        correctness = judge_correctness(q, result) if use_judge else None
        groundedness = judge_groundedness(q, result) if use_judge else None

        summary.results.append(QuestionResult(
            question=q,
            answer=result.answer,
            tools_called=[t.tool for t in result.trace],
            evidence_asset_ids=sorted({e.asset_id for e in result.evidence if e.asset_id}),
            deterministic=det,
            correctness=correctness,
            groundedness=groundedness,
        ))

    summary.total_runtime_s = time.monotonic() - run_start
    return summary


def _result_to_dict(r: QuestionResult) -> dict:
    d = asdict(r)
    return d


def write_results(summary: EvaluationSummary, use_judge: bool) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"eval_{timestamp}.json"

    payload = {
        "timestamp_utc": timestamp,
        "n_questions": summary.n,
        "judge_used": use_judge,
        "total_runtime_s": round(summary.total_runtime_s, 2),
        "avg_latency_s": round(summary.avg_latency_s, 2),
        "aggregate_metrics": {
            "tool_choice_accuracy": summary.tool_choice_accuracy,
            "evidence_overlap_avg": summary.evidence_overlap_avg,
            "abstention_accuracy": summary.abstention_accuracy,
            "keyword_hit_avg": summary.keyword_hit_avg,
            "think_leak_count": summary.think_leak_count,
            "avg_correctness": summary.avg_correctness,
            "avg_groundedness": summary.avg_groundedness,
        },
        "results": [_result_to_dict(r) for r in summary.results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path
