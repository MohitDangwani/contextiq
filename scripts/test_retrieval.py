"""Small, hand-written retrieval test set for the RAG pipeline.

This is NOT the Phase 10 evaluation harness (that covers the whole
agent — tool selection, groundedness, citation accuracy — not just
retrieval). It checks exactly one thing: given a known question, does
semantic_search surface a chunk from the document we expect, within the
top K results? Run after scripts/ingest_documents.py.

Usage:
    python scripts/test_retrieval.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config.database import SessionLocal
from app.rag.retrieval import semantic_search

K = 3

TEST_CASES = [
    {
        "question": "What does customer lifetime value mean?",
        "expected_title_contains": "customer_lifetime_value",
    },
    {
        "question": "What does net revenue mean?",
        "expected_title_contains": "net_revenue",
    },
    {
        "question": "How is revenue recognized at Brightcart?",
        "expected_title_contains": "Revenue Recognition Policy",
    },
    {
        "question": "Are cancelled orders counted as recognized revenue?",
        "expected_title_contains": "Revenue Recognition Policy",
    },
    {
        "question": "What metrics are shown on the revenue dashboard?",
        "expected_title_contains": "Revenue Dashboard Guide",
    },
    {
        "question": "How often is the revenue dashboard refreshed?",
        "expected_title_contains": "Revenue Dashboard Guide",
    },
    {
        "question": "Which datasets are classified as containing PII?",
        "expected_title_contains": "PII Handling Policy",
    },
    {
        "question": "Who is allowed to access PII columns?",
        "expected_title_contains": "PII Handling Policy",
    },
    {
        "question": "What team maintains the customers dataset?",
        "expected_title_contains": "Customers Dataset Overview",
    },
    {
        "question": "Why might the marketing campaigns data look out of date?",
        "expected_title_contains": "Marketing Campaigns Overview",
    },
]


def main() -> None:
    session = SessionLocal()
    passed = 0
    try:
        for case in TEST_CASES:
            results = semantic_search(session, case["question"], k=K)
            titles = [r.title for r in results]
            hit = any(case["expected_title_contains"].lower() in t.lower() for t in titles)
            passed += hit

            print(f"[{'PASS' if hit else 'FAIL'}] {case['question']!r}")
            print(f"    expected (substring): {case['expected_title_contains']!r}")
            print(f"    top-{K} titles: {titles}")
            if results:
                top = results[0]
                print(f"    best match: {top.title!r} (similarity={top.similarity:.3f})")
            print()
    finally:
        session.close()

    total = len(TEST_CASES)
    print(f"Retrieval hit-rate@{K}: {passed}/{total} ({passed / total:.0%})")


if __name__ == "__main__":
    main()
