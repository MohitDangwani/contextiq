"""Loads the Phase 10 benchmark question set from data/evaluation/benchmark.yaml.

Kept as a data file (like data/metadata/*.yaml, data/lineage/lineage.yaml)
rather than hardcoded Python, per the project's existing convention that
domain content lives in data/ and gets loaded by code, not embedded in it.
"""
from pathlib import Path

import yaml

from app.evaluation.schema import BenchmarkQuestion

DEFAULT_BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "evaluation" / "benchmark.yaml"
)


def load_benchmark(path: Path = DEFAULT_BENCHMARK_PATH, limit: int | None = None) -> list[BenchmarkQuestion]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    questions = [
        BenchmarkQuestion(
            id=q["id"],
            category=q["category"],
            question=q["question"],
            expected_answer=q["expected_answer"],
            expected_evidence_asset_ids=q.get("expected_evidence_asset_ids", []),
            expected_tools_any_of=q.get("expected_tools_any_of", []),
            should_abstain=q.get("should_abstain", False),
        )
        for q in raw["questions"]
    ]
    return questions[:limit] if limit is not None else questions
