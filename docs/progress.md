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

## Phase 6.1 — Agent hardening: multi-hop lineage fix + grounded abstention
Two orchestration gaps surfaced while validating the agent against the new
LM Studio + Nemotron 3 Nano 4B provider (GPU-accelerated; see docs/agent.md):

1. **Multi-hop lineage**: `MAX_ITERATIONS=3` left no headroom for a
   genuine 4-tool-call question ("show the lineage from customers to the
   revenue dashboard"), and `force_answer_node` handed the model a
   malformed transcript (a dangling, unresolved `tool_calls` message) with
   no explicit evidence summary -- so hitting the cap produced an
   ungrounded "no evidence available" answer despite real lineage data
   already sitting in `state["evidence"]`.
2. **Grounded abstention**: the existing zero-evidence guardrail (kept
   unchanged, still the hard backstop) only fires when literally nothing
   was retrieved. It doesn't catch the case where the model's own
   exploratory tool calls gather real-but-irrelevant evidence and then
   report that instead of admitting the actual question has no ContextIQ
   answer -- needed a sharper system prompt to close that gap.

Fixes, all in `app/agent/graph.py` unless noted:
- `MAX_ITERATIONS`: 3 -> 4, a reasoned bump (not a blind increase) sized
  to the observed worst case -- Nemotron tends to issue one tool call per
  round rather than batching, and the lineage question needs up to 4.
- `force_answer_node`: closes out any dangling `tool_calls` with an
  explicit "not executed" `ToolMessage` (keeps the transcript well-formed)
  and injects a code-built digest of `state["evidence"]` into the
  reminder, instead of relying on the model to re-derive it from a long
  mixed transcript.
- `agent_node`: bounded (max 2) retry when a turn ends with empty or
  stub-only content (e.g. `"Final Answer:"`) and no tool calls -- a
  distinct failure mode found during testing (`finish_reason: "stop"`,
  most of the token budget unused -- not a budget problem, just an
  incomplete turn that would otherwise silently discard real evidence).
- `SYSTEM_PROMPT`: added explicit no-outside-knowledge, explicit-abstention,
  partial-evidence ("answer what's known, name what's missing"), and
  evidence-relevance ("does what the tools returned actually address what
  was asked?") rules. Kept deliberately short -- an earlier, longer
  version of these rules caused a *new* failure (the model's final turn
  degenerating into "No question was provided." or a bare stub), fixed by
  trimming back down, not by adding more instructions.
- `app/agent/tools.py`: tool dispatch now coerces the literal string
  `"None"` back to a real `None` before it reaches any `_run_*` function.
  Nemotron occasionally serializes an omitted optional argument as that
  string rather than leaving it out; uncorrected, e.g.
  `check_pii(asset_id="None")` silently became a failed lookup for a
  dataset literally named "None" instead of the intended catalog-wide PII
  listing -- a false "not found" caused by a malformed call, not a
  genuine absence of evidence.

7 new regression tests added to `test_agent.py`: multi-hop lineage,
unknown dataset, unknown business metric, out-of-domain question, unknown
documentation, partial evidence, and a guard that the pre-existing
single-hop lineage question still passes. Two pre-existing assertions
(`test_single_tool_owner_question` and the new partial-evidence test) were
loosened to accept `search_assets` as an equally valid path to `get_owner`
-- a real, verified-correct tool-choice difference in how Nemotron answers
ownership questions (it can read the owner straight out of `search_assets`
results), not a correctness regression.

**43/43 passed** (16/16 `test_agent.py` incl. the 7 new tests, 27/27
`test_agent_tools.py`) against live Postgres + live LM Studio/Nemotron,
confirmed stable across repeated full-suite runs. Commit: see below.
