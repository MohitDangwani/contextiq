"""Tests for the Phase 11 chat HTTP endpoint (POST /api/chat).

This does NOT re-test agent behavior -- that's already covered by
tests/test_agent.py, which drives run_agent() directly. This file only
proves the thin HTTP wrapper (app.api.routes.chat) round-trips correctly:
that a real request produces a real response with the expected shape,
including the new grounding_status field.

Real LLM, real Postgres, nothing mocked -- slow (tens of seconds) by
design, same convention as test_agent.py. Kept to 2 tests deliberately.

Run with:
    cd backend && ..\\.venv\\Scripts\\pytest tests/test_api_chat.py -v -s
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_endpoint_returns_grounded_answer():
    response = client.post("/api/chat", json={"question": "Who owns the orders dataset?"})
    assert response.status_code == 200
    body = response.json()

    assert body["grounding_status"] in ("supported", "partial")
    assert body["evidence"], "expected non-empty evidence for a grounded answer"
    assert "sales engineering" in body["answer"].lower()
    # Every trace entry should carry the observable fields the frontend's
    # Agent Activity panel renders -- never anything reasoning-shaped.
    for call in body["trace"]:
        assert {"tool", "input", "output_summary", "timestamp", "evidence_count"} <= call.keys()


def test_chat_endpoint_abstains_on_unanswerable():
    response = client.post("/api/chat", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    body = response.json()

    assert body["grounding_status"] == "not_supported"
    assert "france" not in body["answer"].lower()


def test_chat_endpoint_rejects_empty_question():
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 422
