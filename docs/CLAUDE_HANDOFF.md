# ContextIQ — Session Handoff

Written at the point the previous Claude Code session's context window filled up. This is a from-scratch inspection of the repository at the moment of writing (git, live Docker/Postgres, live LM Studio all checked directly) — not a copy of prior chat summaries. If anything here ever conflicts with the actual repo, the repo wins.

---

## 1. Project Overview

**ContextIQ** is a prototype AI agent that answers natural-language questions about an enterprise data catalog — "Which datasets contain PII?", "Where does monthly revenue come from?", "Is the payments dataset trustworthy?" — by grounding every answer in real metadata, business definitions, lineage, data-quality signals, and documentation, and explicitly abstaining rather than guessing when it can't.

It's a portfolio project demonstrating: RAG/embeddings/vector search, agentic tool use via LangGraph, MCP (planned, not yet built), metadata/lineage/quality modeling, and rigorous evaluation of a local LLM agent — on a Python/FastAPI/Postgres stack.

**Fictional domain:** "Brightcart", an e-commerce company. Seed data: 10 catalog assets (customers, orders, order_items, products, payments, returns, marketing_campaigns, revenue_model, monthly_revenue, revenue_dashboard), real owners/PII flags/quality checks/lineage edges, 2 business terms, 5 documentation files.

**Major components today:**
| Component | Status |
|---|---|
| Database schema + seed data (Postgres) | Built, seeded |
| Context services (`app/services/*`) | Built |
| FastAPI structured-query API | Built (routes only — no agent/chat endpoint) |
| RAG pipeline (chunking, embeddings, pgvector retrieval) | Built |
| LangGraph agent + 8 tools | Built |
| Grounding gate (`verify_support`) | Built (uncommitted) |
| Phase 10 evaluation harness + 30-question benchmark | Built (uncommitted) |
| MCP server | **Not built** — placeholder file only |
| Frontend | **Not built** — empty directories only |
| Docker Compose (full stack) | **Not built** — only the `db` service exists |

---

## 2. Current Architecture

```
data/raw/*.csv, data/metadata/*.yaml, data/lineage/lineage.yaml,          <- source files (Phase 3)
data/documentation/*.md, data/metadata/business_terms.yaml
        |
        v  scripts/seed_database.py
PostgreSQL + pgvector (Docker: contextiq-db-1)                            <- Phase 2 schema
        |
        v
app/services/*.py  (assets, lineage, quality, business_terms,            <- Phase 4 context services;
                     documentation)                                          single source of query logic
        |                                              \
        v                                                v
app/api/routes/* (FastAPI, structured                app/rag/* (chunking, embeddings,
  queries: assets/business_terms/                       retrieval) -> document_chunks
  documentation/search)                                  (pgvector, 384-dim)  [Phase 5]
        |
        (no route wired to the agent yet)
        |
app/agent/tools.py  (8 tools, thin wrappers over the SAME services -- no duplicated logic)
        |
        v
app/agent/graph.py  (LangGraph: agent -> tools -> agent loop, bounded, force_answer safety net)
        |
        v
app/agent/llm.py  ->  LM Studio (OpenAI-compatible) -> Nemotron 3 Nano 4B on RTX 5060
        |               (Ollama/Qwen3 remains as an alternate provider branch, config-selected)
        v
app/agent/run.py  (run_agent(): zero-evidence hard backstop, then
                    app/agent/grounding.py's verify_support() gate)        <- Phase 10.1
        |
        v
Final grounded answer (or explicit abstention)
```

**MCP**: `mcp_server/server.py` is an 8-line placeholder docstring only — Phase 9 was never implemented. The intended design (documented in the file itself and `docs/architecture.md`) is an MCP adapter calling the *same* `app/services/*` functions the API and agent already use — no new business logic, just another interface.

**FastAPI**: `backend/app/main.py` wires up structured query routes (`/api/assets`, `/api/business-terms`, `/api/documentation`, `/api/search`) from Phase 4. Its own docstring is stale — it says "the agent, RAG, MCP, and evaluation endpoints are not built yet", which is only true for the *route* layer. The agent, RAG, and evaluation are all fully functional as importable Python modules (used directly by tests and `scripts/run_evaluation.py`); there is simply no `/api/chat` (or similar) HTTP route exposing `run_agent()` yet. That gap matters for whoever builds Phase 11 (frontend needs *something* to call).

**Evaluation**: `app/evaluation/*` + `scripts/run_evaluation.py` + `data/evaluation/benchmark.yaml` — a standalone harness, not wired into the API. Full detail in section 9.

---

## 3. Completed Phases

| # | What | Key files | Key decisions | Tests | Commit |
|---|---|---|---|---|---|
| 1 | Repo scaffold, FastAPI health check | `backend/app/main.py` | Monorepo layout decided up front (`docs/architecture.md`) | — | `7b64a4b` |
| 2 | DB schema | `backend/app/models/*.py` | 9 SQLAlchemy models + join table; verified against live Postgres | — | `54c8f6b` |
| 3 | Sample data | `data/raw/*.csv`, `scripts/seed_database.py` | Fictional "Brightcart" dataset: 7 raw tables, 10 catalog assets, 8 lineage edges, 5 docs, 2 business terms | — | `57bffb5` |
| 4 | Context services + API | `backend/app/services/*.py`, `backend/app/api/*` | Service layer is the *only* place query logic lives — API, agent, and (future) MCP all call into it, never duplicate it | — | `22d3068` |
| 5 | RAG pipeline | `backend/app/rag/*.py` | Local embeddings (`sentence-transformers/all-MiniLM-L6-v2`, 384-dim) — no API key was available; chose hit-rate@3 not @1 as the honest metric | 10/10 hit-rate@3 (`scripts/test_retrieval.py`) | `49e8a45` |
| 6 | LangGraph agent | `backend/app/agent/{graph,run,state,text,tools,llm}.py` | 8 tools wrapping Phase 4/5 services; code-enforced zero-evidence backstop (not just prompted); `<think>`-tag stripping as defense-in-depth | 9/9 (`test_agent.py`, original set) | `82400a8` |
| 7 | Orchestration checkpoint | — | No new code — verification checkpoint for the master spec's own phase numbering, folded into Phase 6's commit | (same as Phase 6) | `82400a8` |
| 8 | Independent tool tests | `backend/tests/test_agent_tools.py` | Each tool's `_run_*` function tested directly, no LLM — the "every tool independently testable" requirement | 27/27 (original), now 38/38 with later additions | `f83d2b6` |
| 9 | MCP server | — | **Not implemented.** Still the Phase 1 placeholder. | — | — |
| **6.1** | Agent hardening (in the same commit as "Integrate Nemotron...") | `backend/app/agent/graph.py`, `tools.py` | Multi-hop lineage termination fix (`MAX_ITERATIONS` 3→4 + `force_answer` evidence digest + dangling-tool-call closure); grounded-abstention prompt rules; literal-`"None"` tool-argument sanitization | 16/16 `test_agent.py` (incl. 7 new), 27/27 `test_agent_tools.py` | `17b5a3a` |
| **10** | Evaluation harness | `backend/app/evaluation/*.py`, `scripts/run_evaluation.py`, `data/evaluation/benchmark.yaml` | 30-question benchmark, deterministic metrics + LLM judge (separate correctness/groundedness calls), reused agent-provider infra for the judge | 16/16 `test_evaluation.py` | **uncommitted** |
| **10.1** | Grounding architecture redesign | `backend/app/agent/grounding.py` (new), `run.py`, `state.py`, `text.py` | Replaced "evidence exists ⇒ trust it" with a code-enforced `verify_support()` gate — see sections 7-8 | 6/6 `test_grounding.py`, 30/30 questions with 1.00 abstention_accuracy | **uncommitted** |

Only `17b5a3a` ("Integrate Nemotron and strengthen agent grounding") — which bundles the LM Studio/Nemotron provider switch *and* Phase 6.1's agent hardening — is the current `HEAD`. Everything from Phase 10 onward is **uncommitted working-tree changes** (see section 11).

---

## 4. Current LLM Setup

- **Provider:** LM Studio, OpenAI-compatible local server.
- **Model:** `nvidia/nemotron-3-nano-4b` (2.84 GB, Q4 quantization).
- **Endpoint:** `http://127.0.0.1:1234/v1` (confirmed live: `Server: ON (port: 1234)`).
- **GPU:** NVIDIA GeForce RTX 5060 Laptop GPU, 8151 MiB total VRAM, driver 610.74. Confirmed model is GPU-resident (~4.3 GB VRAM used during inference vs. ~1.2 GB idle baseline).
- **Runtime engine:** `llama.cpp-win-x86_64-nvidia-cuda12-avx2@2.28.2` — **must stay selected**. The older `nvidia-cuda-avx2@2.25.2` engine hangs indefinitely and then aborts when loading this model on this GPU (a Blackwell-generation card); the CUDA-12-specific build is the one that actually works. Verify with `lms runtime ls` — the `✓` must be on the `cuda12` line.
- **Context length:** loaded at 8192 (model's architectural max is far higher, but 8192 is what's configured and tested against).
- **Parallel slots:** 4.
- **Tool-calling:** confirmed working — clean OpenAI-compatible `tool_calls` structure, consumed correctly by LangGraph throughout every phase above.
- **Reasoning behavior:** Nemotron emits hidden chain-of-thought in a separate `reasoning_content` field before its actual `content`/tool call. This is *not* leaked into `content` (confirmed — `think_leak_count: 0` across all 30 benchmark questions), but it does consume real completion-token budget, which is why `llm_max_tokens=2048` is set generously (a tight budget previously caused empty-content failures).
- **Approximate performance:** ~30-45 tokens/sec generation; ~7-8s average per full agent question (including tool calls and, since Phase 10.1, one extra grounding-verification LLM call).

**Ollama/Qwen3:** `qwen3:4b` via Ollama was the *original* provider, used on a previous machine, and remains a fully intact, config-selected fallback branch in `app/agent/llm.py` (`llm_provider == "ollama"`). It was **not** re-verified on this machine and Ollama is **not installed here**. Do not install Ollama or download Qwen3 on this machine — LM Studio + Nemotron is the current, working, GPU-accelerated setup.

---

## 5. Database

- **Engine:** PostgreSQL 16 + pgvector extension (`pgvector/pgvector:pg16` Docker image), extension version 0.8.6.
- **Container:** `contextiq-db-1`, defined in `docker-compose.yml` (the `db` service only — no `backend`/`mcp_server`/`frontend` services exist in compose yet).
- **Schema:** 9 SQLAlchemy models under `backend/app/models/`: `Asset`, `Owner`, `Tag` (+ join table), `DatasetColumn`, `BusinessTerm`, `LineageEdge`, `DataQualityCheck`, `Documentation`, `DocumentChunk` (the RAG index table, `vector(384)` column).
- **Current live state (verified just now):** container up, `SELECT count(*) FROM assets` → 10, `SELECT count(*) FROM document_chunks` → 22.
- **Start the DB:**
  ```bash
  docker start contextiq-db-1
  ```
  (If the container doesn't exist yet: `docker compose up -d db` from the repo root.)
- **Verify it's running:**
  ```bash
  docker exec contextiq-db-1 pg_isready -U contextiq
  docker exec contextiq-db-1 psql -U contextiq -d contextiq -c "SELECT count(*) FROM assets;"
  ```
- **Seed from scratch** (idempotent, safe to re-run):
  ```bash
  python scripts/init_db.py
  python scripts/seed_database.py
  python scripts/ingest_documents.py
  ```
- **Key environment variables** (`.env.example`; no `.env` file currently exists in the repo — defaults in `settings.py` match the Docker Compose defaults, so nothing needs to be set for local dev unless you want to override):
  `DATABASE_URL` (default `postgresql+psycopg2://contextiq:contextiq@localhost:5432/contextiq`), `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` (all default `contextiq`).

---

## 6. RAG

- **Source files:** `data/documentation/*.md` (5 files) + `data/metadata/business_terms.yaml` (2 terms) — both loaded into Postgres by `scripts/seed_database.py`; the RAG index is built *from those Postgres rows*, not from the files directly.
- **Chunking** (`app/rag/chunking.py`): splits Markdown on `##` headers first (topic-coherent chunks), then a sliding window (`MAX_CHARS=800`, `OVERLAP_CHARS=100`) for any section still too long. Hand-rolled, not a library — deliberate, since the source docs are short.
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, runs fully local/offline (no API key was available when this was built). `EMBEDDING_DIM = 384` in `app/models/chunk.py`.
- **Storage:** `document_chunks` table, `pgvector` `Vector(384)` column, each row self-describing (denormalized `title`/`asset_id`/`source_url` for citation without a join).
- **Retrieval** (`app/rag/retrieval.py`): `semantic_search()` — embeds the query, cosine-distance ORDER BY, optional `asset_id` scoping.
- **Filtering:** `DOC_SIMILARITY_THRESHOLD = 0.35` in `app/agent/tools.py` — hits below this are dropped as noise before ever becoming agent evidence.
- **Tests:** `scripts/test_retrieval.py` — 10 hand-written questions, **10/10 hit-rate@3** last verified.
- **Known limitations (documented honestly in `docs/rag.md`):** the small local embedding model is weaker on paraphrased queries than a hosted model would be — one of the 10 test questions retrieved the *correct* document only at rank 2, not rank 1 (still within hit-rate@3). `app/rag/retrieval.py` is not called from `app/api` directly — it's used only via the agent's `search_documentation` tool.

---

## 7. Agent

- **`AgentState`** (`app/agent/state.py`, TypedDict): `messages` (LangGraph message list), `question`, `trace: list[ToolInvocation]`, `evidence: list[EvidenceItem]`, `iterations: int`.
  - `ToolInvocation` gained an `evidence_count: int` field in Phase 10.1 — `len(evidence)` produced by that specific call, letting downstream code tell "this lookup found nothing" apart from "something else was found elsewhere" without re-parsing free text.
  - `evidence_digest(evidence)` — one shared formatting function (moved here in Phase 10.1) used everywhere evidence needs to be handed back to an LLM call.
- **8 tools** (`app/agent/tools.py`), each a thin wrapper over `app/services/*` or RAG, returning `ToolResult(summary, evidence)`: `search_assets`, `get_schema`, `get_owner`, `check_pii`, `get_lineage`, `check_quality`, `get_business_definition`, `search_documentation`.
  - `_sanitize_args()` — coerces the literal string `"None"`/`"null"` (Nemotron occasionally serializes an omitted optional argument this way) back to real `None` before any tool function sees it. Found and fixed in Phase 6.1; a real, reproduced bug, not speculative.
  - `get_lineage`'s evidence lines state each hop's own direct edge explicitly (`"orders -> order_items, via: foreign key..."`) rather than just "N hops away via TRANSFORMATION" — fixes a real lineage relationship-type mixup where the model misattributed one edge's transformation to an adjacent edge when narrating a multi-hop chain. Backed by `LineageHop.via_asset_id` in `app/services/lineage.py`.
- **LangGraph flow** (`app/agent/graph.py`): `agent` node (LLM decides tool calls) → `tools` node (executes, appends to `trace`/`evidence`) → loop back to `agent`, bounded by `MAX_ITERATIONS = 4` (raised from 3 — sized to the observed worst case: Nemotron issues one tool call per round rather than batching, and a genuine multi-hop lineage question needs up to 4).
- **`force_answer`**: safety net if the model still wants tools after 4 rounds. Closes out any dangling unresolved `tool_calls` with an explicit "not executed" `ToolMessage` (a malformed transcript was previously making the model think nothing had been found at all), and hands over a code-built digest of `state["evidence"]` rather than asking the model to re-derive it from a long transcript.
- **Retries:** `agent_node` has a bounded (max 2) retry when a turn ends with empty/stub content (`_looks_incomplete()` — catches empty strings, bare headers like `"Final Answer:"`, and — only when evidence exists — generic give-up phrases like `"unable to determine"`). This is a *text-shape* check, orthogonal to and independent of the grounding gate below.
- **Thinking-token stripping:** `app/agent/text.strip_thinking()` removes `<think>...</think>` blocks defensively (verified `content` is already clean for Nemotron via LM Studio, but applied everywhere as defense-in-depth regardless of provider).
- **Evidence handling:** every tool call's `EvidenceItem`s are appended to a flat `state["evidence"]` list for the whole run — historically this list meant only "something was found this turn," which is exactly the gap the grounding gate closes (see section 8).
- **Grounding gate — why it exists:** every fix through Phase 10 (polarity consistency, lineage evidence clarity, give-up retries) was real and correct, but a distinct failure kept resurfacing on a *different* question each time: the model gathering real, correctly-cited evidence about something *unrelated* to the actual question, and answering from it anyway instead of abstaining (e.g. asked about a disaster-recovery policy, answering with the dataset's PII columns instead). `run.py`'s only code-enforced guarantee was `if evidence: trust it / else: abstain` — evidence being non-empty never meant "evidence that answers this question." No amount of prompt tweaking permanently closed that, because the code was never checking relevance at all. See section 8 for the fix.

---

## 8. Grounding / Safety

```
zero evidence  ------------------------------------------> NOT_FOUND_MESSAGE   (hard backstop, unchanged since Phase 6)
non-empty evidence -> verify_support() -> "not_supported" -> NOT_FOUND_MESSAGE
                                        -> "supported"/"partial" -> the model's own drafted answer
```

- **Zero-evidence backstop** (`app/agent/run.py`, untouched since Phase 6): if `state["evidence"]` is empty, the answer is unconditionally `NOT_FOUND_MESSAGE`, regardless of what the model's own text said. Fully deterministic, no LLM involved.
- **`verify_support()`** (`app/agent/grounding.py`, new in Phase 10.1): when evidence is non-empty, a **separate, single-purpose LLM classification call** (same pattern as the Phase 10 judge, not a bullet added to the main agent's already-crowded prompt) classifies the gathered evidence against the question as `supported` / `partial` / `not_supported`. The *decision* of what happens next is 100% code (`run.py`), never left to the main agent to self-police.
  - Also receives an "unresolved lookups" digest — specific tool calls whose `evidence_count == 0` — so a targeted "not found" result has explicit structural weight, not just buried text.
  - The prompt explicitly separates "right entity" from "right attribute": evidence about the *correct* dataset but the *wrong* topic (e.g. PII status when asked about a backup policy) is still `not_supported`. This distinction was added after a real failure surfaced during testing — the first version of the prompt only reliably caught *wrong-entity* evidence, not *right-entity-wrong-attribute* evidence.
- **Fail-closed:** if the verifier's response fails to parse, or the call throws for any reason, the result is `not_supported` → abstain. A broken classifier can only make the system more cautious, never less safe.
- **Irrelevant evidence protection:** directly tested (`test_irrelevant_evidence_is_not_supported`, `test_right_entity_wrong_attribute_is_not_supported`) and confirmed in the live 30-question benchmark (the historically flakiest question, about a disaster-recovery policy, cleanly abstained with zero evidence retained in the final run).
- **Partial evidence handling:** classified `partial`, and the model's own draft (already prompted to separate known-vs-unavailable) is used as-is — the gate doesn't rewrite the answer, it only prevents `not_supported` drafts from being trusted. Directly tested (`test_partial_evidence_is_classified_partial`) and confirmed symmetrically (`test_fully_answered_multi_part_question_is_supported` — the gate doesn't default to over-cautious).
- **Out-of-domain / unknown-dataset handling:** these typically produce zero evidence (the model correctly declines to call tools, or a targeted lookup returns nothing) and hit the hard backstop directly; if any stray evidence is gathered, the gate is the second line of defense.
- **No outside/pretrained knowledge:** enforced by both the zero-evidence backstop and the grounding gate (a `not_supported` verdict discards the draft regardless of how plausible it sounds) — confirmed empirically across every abstention-category question in the final benchmark run, zero exceptions.
- **What `flags_gap()`/`GAP_PHRASES` (`app/agent/text.py`) is NOT:** a phrase-matching heuristic used *only* for the Phase 10 harness's own measurement and test assertions — explicitly documented as never to be wired into runtime enforcement, because phrase-matching a model's free-text wording already needed three separate corrections this project for being too brittle to trust with a safety-critical decision.

---

## 9. Evaluation

- **Benchmark:** `data/evaluation/benchmark.yaml` — **30 questions**, every `expected_*` field checked directly against the live seeded database (never invented). Categories: known_factual, multi_tool, lineage, lineage_multi_hop, quality, pii, business_definition, tool_use_schema, documentation, and 5 abstention variants (unknown_dataset, unknown_metric ×2, unknown_documentation, out_of_domain ×2, partial_evidence).
- **Runner:** `scripts/run_evaluation.py` (CLI: `--limit N`, `--judge`) → `app/evaluation/runner.py` → calls the **real** `run_agent()` for every question, no mocks.
- **Deterministic metrics** (`app/evaluation/deterministic.py`, no LLM call): `tool_choice_correct`, `evidence_overlap`, `abstention_correct`, `keyword_hit`, `think_leak`, `latency_s`.
- **LLM judge** (`app/evaluation/judge.py`): two separate calls — **correctness** (vs. the benchmark's gold `expected_answer`) and **groundedness** (vs. the agent's own retrieved evidence, a deliberately different reference) — each scored 0/1/2, JSON-only, parsed defensively via the shared `extract_json_object()` in `app/agent/text.py`.
- **Final 30-question result** (real LM Studio + Nemotron + live Postgres, `data/evaluation/results/eval_20260818T141654Z.json`):
  ```
  30/30 completed, 0 crashes
  tool_choice_accuracy  = 1.00
  evidence_overlap_avg  = 1.00
  abstention_accuracy   = 1.00   (first perfect score all project)
  keyword_hit_avg       = 0.67
  think_leak_count      = 0
  avg_correctness       = 1.97/2  (29× 2/2, 1× 1/2, 0× 0/2)
  avg_groundedness      = 1.90/2  (27× 2/2, 3× 1/2, 0× 0/2)
  Total runtime: 360.3s, avg 7.41s/question
  ```
- **The 4 non-perfect scores, and why they're not application bugs:**
  - **q03** (correctness 1/2): named only the immediate upstream hop (`monthly_revenue`) rather than the fuller reference chain. **Model limitation/variance (E)** — this exact narrower-vs-fuller pattern recurred across *every* run this project regardless of other fixes; the question's own phrasing ("where does X's data come from") doesn't strictly require walking the full chain.
  - **q12** (groundedness 1/2): judge's stated reasoning claims the answer "contradicts the evidence showing monthly_revenue has a quality_score" — but the answer correctly said *revenue_dashboard* (a different asset in the same lineage) has no recorded quality checks, which is true. **Evaluation/judge limitation (C)** — the judge's own reasoning doesn't support its score.
  - **q22** (groundedness 1/2): docked for "adding a claim about GDPR retention period" — the claim was "the catalog does not contain documentation about X," i.e. correctly reporting absence, not inventing a value. **Evaluation/judge limitation (C)**.
  - **q24** (groundedness 1/2): judge's own reasoning states the answer "cites the quality score and freshness warning directly from evidence" — doesn't logically support a deduction. **Evaluation/judge limitation (C)**.
  - Zero questions were classified as application bugs, tool/evidence-presentation bugs, or test brittleness in the final run.
- **Known limitations of the judge itself:** it's the *same* 4B Nemotron model scoring its own family's outputs, not an independent/larger judge — treat absolute scores as directional signal, not ground truth. It has shown internally-inconsistent reasoning (stating a fact that contradicts its own score) on at least 3 occasions across this project.
- **Tests:** `backend/tests/test_evaluation.py` (16 tests: benchmark loading, deterministic metrics, judge JSON parsing — no LLM/DB needed) and `backend/tests/test_grounding.py` (6 tests: the grounding gate itself, needs LLM but synthetic evidence, no DB).

---

## 10. Tests

**Latest known results (all verified live this session, LM Studio + Nemotron, live Postgres):**
| Suite | File | Result |
|---|---|---|
| Phase 6 (agent, full LLM loop) | `backend/tests/test_agent.py` | **18/18** |
| Phase 8 (tools, direct calls) | `backend/tests/test_agent_tools.py` | **38/38** |
| Evaluation harness (no LLM/DB) | `backend/tests/test_evaluation.py` | **16/16** |
| Grounding gate (LLM, synthetic evidence) | `backend/tests/test_grounding.py` | **6/6** |
| **Total** | | **78/78** |

**Stability testing performed** (not "passed once"): Phase 6 ran clean 4 consecutive full times after the final grounding-prompt fix (72/72 individual passes). A targeted 12-run stress test of the three historically flakiest questions passed 11/12 — the one failure (an isolated wrong-tool-selection anomaly on a normally-reliable question) did **not** reproduce across 4 immediate isolated follow-up runs of the exact same question, and is documented as a rare, non-systemic model-variance event, not a gate failure. The grounding gate's own unit suite ran clean twice.

Run commands:
```bash
cd backend
export LLM_PROVIDER=lmstudio   # PowerShell: $env:LLM_PROVIDER = "lmstudio"
../.venv/Scripts/python.exe -m pytest tests/test_agent_tools.py -v
../.venv/Scripts/python.exe -m pytest tests/test_evaluation.py -v
../.venv/Scripts/python.exe -m pytest tests/test_grounding.py -v
../.venv/Scripts/python.exe -m pytest tests/test_agent.py -v   # slow: ~2.5-3.5 min, real LLM loop
```

---

## 11. Git State

**Directly inspected just now — do not trust any earlier report over this:**

- **HEAD:** `17b5a3aa96e1dc1656c8dded85b1318b88128848` ("Integrate Nemotron and strengthen agent grounding")
- **Branch:** `main`
- **`origin/main`:** identical to HEAD (`17b5a3aa...`) — **0 ahead, 0 behind**. Everything through that commit is already pushed.
- **Working tree: DIRTY.** `git status`:
  ```
  Changes not staged for commit (12 files):
    modified:   backend/app/agent/graph.py
    modified:   backend/app/agent/run.py
    modified:   backend/app/agent/state.py
    modified:   backend/app/agent/text.py
    modified:   backend/app/agent/tools.py
    modified:   backend/app/evaluation/__init__.py
    modified:   backend/app/services/lineage.py
    modified:   backend/tests/test_agent.py
    modified:   backend/tests/test_agent_tools.py
    modified:   docs/agent.md
    modified:   docs/evaluation.md
    modified:   docs/progress.md

  Untracked files (10):
    backend/app/agent/grounding.py
    backend/app/evaluation/benchmark.py
    backend/app/evaluation/deterministic.py
    backend/app/evaluation/judge.py
    backend/app/evaluation/runner.py
    backend/app/evaluation/schema.py
    backend/tests/test_evaluation.py
    backend/tests/test_grounding.py
    data/evaluation/benchmark.yaml
    scripts/run_evaluation.py
  ```
- **`git diff --check`:** clean (exit 0) — only harmless LF→CRLF line-ending notices, no real whitespace errors.
- **What this represents:** the *entire* Phase 10 evaluation harness build, the Phase 10.1 grounding architecture redesign, and every regression test added along the way — none of it committed yet. `data/evaluation/results/*.json` (5 files, latest `eval_20260818T141654Z.json`) exist on disk but are gitignored, not tracked.

---

## 12. Remaining Phases

Based on `docs/architecture.md`'s stated build order ("data model first, then services, then retrieval, then the agent, then interfaces, then evaluation and hardening last") and the repository structure already scaffolded:

- **Phase 11 — Frontend.** `frontend/src/{components,pages,services}` exist but are empty. Needs a chat UI calling the agent — and since no `/api/chat` route exists yet, this phase likely also needs a thin FastAPI route wrapping `run_agent()` first (not yet decided/designed).
- **Phase 12 — Lineage visualization.** No code yet. Would consume `get_lineage`'s existing structured output (`LineageResult`/`LineageHop`, already includes `via_asset_id` for exact edges) — the data shape may already be sufficient, worth checking before building new lineage-traversal code.
- **Phase 13 — Testing.** `allow_destructive_sql` already exists as a settings flag (currently unused by any implemented tool — no `run_sql` tool exists yet). The name suggests broader hardening/security testing beyond what Phase 6/8/10 already cover.
- **Phase 14 — Logging/observability.** No structured logging beyond Python defaults exists yet. `docker-compose.yml`'s own comment says it will be "finalized in Phase 14 (Deployment)" — there may be some overlap/renumbering to reconcile between the doc's phase list and this handoff's.
- **Phase 15 — Docker/deployment.** `docker-compose.yml` currently only defines the `db` service; its own comments already sketch `backend`, `mcp_server`, `frontend` services to be filled in.
- **Phase 16 — Documentation.** `README.md` is currently stale (still says "Status: Phase 1 complete") and would need a full pass reflecting Phases 1-10.1.
- **Phase 17 — Demo preparation.** No content yet — would follow once the above are functional.

None of these have been started. Do not begin any of them until the immediate next step (section 13) is complete and approved.

---

## 13. Immediate Next Step

**Do NOT start Phase 11 or any later phase.**

The next session's first action must be a **read-only code review of the current uncommitted changes** (the 12 modified + 10 untracked files listed in section 11):
1. Re-inspect the diff for the Phase 10 evaluation harness and the Phase 10.1 grounding gate.
2. Run the four test suites in section 10 and confirm the reported results still hold (they were last verified at the end of this session, but should be reconfirmed fresh in the new session before trusting them).
3. Report findings to the user.
4. **Wait for explicit approval before staging/committing anything.**

Only after that review and explicit approval should committing be considered — and even then, only if the user asks for it. Do not commit or push as part of "cleaning up" the handoff.

---

## 14. Important Engineering Rules

These are hard-won from this project's actual history (see section 3, Phase 10.1) — violating them reintroduces exactly the whack-a-mole cycle that Phase 10.1 was built to end.

- Do not chase individual benchmark questions indefinitely.
- Fix general architectural problems, not benchmark-specific symptoms.
- Never hardcode benchmark questions/answers into production code.
- Never weaken grounding to improve evaluation scores.
- Never use outside/pretrained knowledge to fill missing enterprise information.
- Fail closed when grounding verification fails (unparseable/erroring verifier response → `not_supported`, always).
- Keep business logic in shared service layers (`app/services/*`) — API, agent, and any future MCP implementation call into it, never duplicate it.
- Do not duplicate logic between API, agent, and MCP.
- Keep LM Studio/Nemotron as the current provider.
- Do not install Ollama on this machine.
- Do not download Qwen3 on this machine.
- Do not modify LM Studio configuration unless explicitly requested (the CUDA12 engine selection in particular — see section 4 — is load-bearing; don't let it silently drift back to a CPU or older CUDA engine).
- Do not commit or push without explicit approval.
- Run tests after meaningful changes.
- Do not start later phases while an earlier checkpoint has unresolved blocking issues.
- Prefer generalizable fixes over benchmark-specific patches — when in doubt, ask whether a fix would still make sense if the specific benchmark question were deleted.

---

## 15. Environment / Startup

All commands below were run and verified working on this machine during this session.

**Start Docker Desktop** (if not already running):
```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

**Verify Docker:**
```bash
"/c/Program Files/Docker/Docker/resources/bin/docker.exe" ps
```

**Start PostgreSQL:**
```bash
docker start contextiq-db-1
# or, if the container doesn't exist yet, from the repo root:
docker compose up -d db
```

**Verify PostgreSQL:**
```bash
docker exec contextiq-db-1 pg_isready -U contextiq
docker exec contextiq-db-1 psql -U contextiq -d contextiq -c "SELECT count(*) FROM assets;"
```

**Activate the Python environment** (venv already exists at repo root):
```bash
cd /path/to/contextiq
source .venv/Scripts/activate      # bash
# or in PowerShell: .venv\Scripts\Activate.ps1
```

**Start the backend** (structured-query API only — no agent route exists):
```bash
cd backend
uvicorn app.main:app --reload
```

**Verify LM Studio:**
```bash
"/c/Users/mohit/.lmstudio/bin/lms.exe" status
"/c/Users/mohit/.lmstudio/bin/lms.exe" ps
# If not loaded:
"/c/Users/mohit/.lmstudio/bin/lms.exe" load nvidia/nemotron-3-nano-4b --gpu max -c 8192 -y
```

**Set the provider for any agent/eval/test run** (no `.env` file exists; set per-shell):
```bash
export LLM_PROVIDER=lmstudio          # bash
$env:LLM_PROVIDER = "lmstudio"        # PowerShell
```

**Run tests** (from `backend/`, with `LLM_PROVIDER` set and DB running):
```bash
../.venv/Scripts/python.exe -m pytest tests/test_agent_tools.py -v
../.venv/Scripts/python.exe -m pytest tests/test_evaluation.py -v
../.venv/Scripts/python.exe -m pytest tests/test_grounding.py -v
../.venv/Scripts/python.exe -m pytest tests/test_agent.py -v
```

**Run the evaluation** (from repo root):
```bash
source .venv/Scripts/activate
export LLM_PROVIDER=lmstudio
export PYTHONIOENCODING=utf-8   # avoids console mangling of non-ASCII characters on Windows
python scripts/run_evaluation.py --limit 8 --judge     # quick smoke subset
python scripts/run_evaluation.py --judge               # full 30-question benchmark
```

---

## 16. Known Limitations

Documented honestly, not hidden:

- **The grounding gate is a code-enforced decision fed by an LLM judgment, not a mathematical guarantee.** The zero-evidence backstop is airtight; the irrelevant-evidence path depends on a 4B model's classification, verified stable across many runs but not provably perfect. One real misclassification (same-entity-wrong-attribute) was found and fixed during Phase 10.1 testing — there is no guarantee an equally subtle case doesn't exist undiscovered.
- **The Phase 10 judge scores its own model family.** Not an independent evaluator; shown to produce internally-inconsistent reasoning (stating a fact that contradicts its own score) on at least 3 occasions. Treat absolute scores as directional.
- **RAG embeddings are a small local model**, weaker than a hosted model on paraphrased queries (documented in `docs/rag.md` with a concrete example).
- **No FastAPI route exposes the agent yet** — `run_agent()` is only callable from Python (tests, scripts, a future route). Phase 11 will need to decide whether to add this as part of itself or as a small preceding step.
- **MCP is entirely unimplemented** — a docstring placeholder only.
- **No frontend exists** — empty directories only.
- **`docker-compose.yml` only defines the database service** — no containerized backend, MCP, or frontend yet.
- **`README.md` is stale** (says "Phase 1 complete").
- **One non-reproducible test anomaly** was observed during Phase 10.1 stress testing (a single wrong-tool-selection event that didn't recur in 4 immediate follow-up attempts) — documented, not silently dismissed, but also not chased further given it couldn't be reproduced.
- **Extra latency from the grounding gate**: every `run_agent()` call now makes one additional LLM call (the verifier) whenever evidence is non-empty, on top of the agent's own tool-calling rounds. This roughly matches or modestly increases total latency (observed avg 7.41s/question in the final benchmark, in line with pre-gate averages) but is a real, permanent cost of the safety property it buys.
- **No `.env` file exists in this repo** — all current runs rely on `settings.py`'s defaults plus ad hoc shell environment variables (`LLM_PROVIDER=lmstudio`). Anyone continuing this project should decide whether to commit a real `.env` workflow or keep relying on shell exports.
