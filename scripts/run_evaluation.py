"""Phase 10 evaluation runner: scores the real ContextIQ agent against
data/evaluation/benchmark.yaml.

No mocks -- every question runs the real LangGraph agent against the
configured LLM_PROVIDER (see .env / app/config/settings.py) and the real
seeded Postgres database.

Usage:
    python scripts/run_evaluation.py                  # full 30-question benchmark, deterministic only
    python scripts/run_evaluation.py --limit 8         # first 8 questions, deterministic only
    python scripts/run_evaluation.py --limit 8 --judge # first 8 questions + LLM correctness/groundedness judge

--judge adds two extra LLM calls per question (correctness + groundedness),
roughly doubling runtime -- off by default so a quick deterministic-only
pass stays fast.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.evaluation.runner import run_evaluation, write_results  # noqa: E402


def _fmt(value, digits=2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N benchmark questions.")
    parser.add_argument("--judge", action="store_true", help="Also run the LLM correctness/groundedness judge.")
    args = parser.parse_args()

    print(f"Running ContextIQ Phase 10 evaluation "
          f"({'first ' + str(args.limit) if args.limit else 'all'} questions, "
          f"judge={'on' if args.judge else 'off'})...\n")

    summary = run_evaluation(limit=args.limit, use_judge=args.judge)

    for r in summary.results:
        det = r.deterministic
        tag = "ABSTAIN-OK" if r.question.should_abstain and det.abstention_correct else \
              "ABSTAIN-FAIL" if r.question.should_abstain else \
              "OK" if det.abstention_correct else "FAIL"
        print(f"[{tag}] {r.question.id} ({r.question.category}) — {r.question.question}")
        print(f"    tools: {r.tools_called}  evidence: {r.evidence_asset_ids}  latency: {det.latency_s:.2f}s")
        print(f"    keyword_hit={_fmt(det.keyword_hit)}  tool_choice_correct={_fmt(det.tool_choice_correct)}  "
              f"evidence_overlap={_fmt(det.evidence_overlap)}")
        if r.correctness or r.groundedness:
            c = f"{r.correctness.score}/2 ({r.correctness.reasoning})" if r.correctness else "n/a"
            g = f"{r.groundedness.score}/2 ({r.groundedness.reasoning})" if r.groundedness else "n/a"
            print(f"    judge: correctness={c}  groundedness={g}")
        print(f"    answer: {r.answer[:200]}")
        print()

    print("=" * 70)
    print(f"Questions: {summary.n}   Total runtime: {summary.total_runtime_s:.1f}s   "
          f"Avg/question: {summary.avg_latency_s:.2f}s")
    print(f"Deterministic -- tool_choice_accuracy: {_fmt(summary.tool_choice_accuracy)}  "
          f"evidence_overlap_avg: {_fmt(summary.evidence_overlap_avg)}  "
          f"abstention_accuracy: {_fmt(summary.abstention_accuracy)}  "
          f"keyword_hit_avg: {_fmt(summary.keyword_hit_avg)}  "
          f"think_leak_count: {summary.think_leak_count}")
    if args.judge:
        print(f"LLM judge -- avg_correctness: {_fmt(summary.avg_correctness)}/2  "
              f"avg_groundedness: {_fmt(summary.avg_groundedness)}/2")

    path = write_results(summary, use_judge=args.judge)
    print(f"\nResults written to: {path}")


if __name__ == "__main__":
    main()
