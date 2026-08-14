# Progress log

Concise, append-only summary of each phase's delivery. See docs/architecture.md,
docs/rag.md, docs/agent.md for full explanations; this file is the quick-scan index.

## Phase 1 — Repository + architecture
Monorepo scaffold, FastAPI health-check stub. Commit `7b64a4b`.

## Phase 2 — Database schema
9 SQLAlchemy models (Asset, Owner, Tag, DatasetColumn, BusinessTerm, LineageEdge,
DataQualityCheck, Documentation + join table). Verified against live Postgres.
Commit `54c8f6b`.

## Phase 3 — Sample enterprise data
Fictional "Brightcart" e-commerce data: 7 raw CSVs loaded into a `raw` Postgres
schema, 10 catalog assets (7 tables + revenue_model/monthly_revenue/revenue_dashboard),
8 lineage edges, 5 documentation files, 2 business terms. `scripts/seed_database.py`.
Commit `57bffb5`.

## Phase 4 — Context services and API
Service layer (`app/services/`) + FastAPI routes (`app/api/`), 12 endpoints, all
verified against live Postgres. Commit `22d3068`.

## Phase 5 — RAG pipeline
Chunking + local embeddings (sentence-transformers, no API key available) +
pgvector storage + semantic_search. 22 chunks indexed, 10/10 retrieval
hit-rate@3 on a hand-written test set. Commit `49e8a45`.

## Phase 6 — LangGraph agent (orig. spec Phase 7 + 8, merged)
LangGraph agent using Qwen3:4B via Ollama (local, no API key available;
researched against 15.7GB RAM / Iris Xe CPU-only hardware). 8 tools wrapping
Phase 4/5 services, multi-step tool-calling loop, code-enforced grounding
(zero evidence -> guaranteed "could not find" answer, not just prompted).
9/9 integration tests passed against live Postgres + live Ollama
(~25 min total, CPU inference). Commit `82400a8`.

## Phase 7 — Agent orchestration (verification checkpoint)
No new code: this is the original master spec's "Phase 7: Agent" item,
already fully delivered and tested as part of the Phase 6 commit above
(`app/agent/graph.py`, `run.py`, `state.py`, `llm.py`, `text.py`). The 9/9
`tests/test_agent.py` results are its verification. Documented here as a
separate checkpoint per the phase-tracking request, not a separate commit.

## Phase 8 — Agent tool layer: independent tool tests
Added `backend/tests/test_agent_tools.py`: 27 fast (23s total, no LLM)
unit tests calling each tool's `run()` directly against live Postgres --
covers structured output, not-found/error handling, and input validation
(missing required args raise `pydantic.ValidationError`) for all 8 tools.
Satisfies the original spec's "each tool must be independently testable"
requirement, which the LLM-driven `test_agent.py` suite alone didn't cover.
27/27 passed. Commit: see below.
