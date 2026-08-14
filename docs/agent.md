# Agent

## The problem

Phase 4's API answers one structured question at a time — one endpoint,
one capability. A real user doesn't ask in those terms: "is the revenue
dashboard trustworthy *and* where does its data come from?" needs two
different capabilities (quality + lineage) combined into one answer. The
agent's job is to read a free-text question, figure out which of
ContextIQ's capabilities it actually needs (not all of them, every time),
call those, and produce one grounded answer with citations.

## Architecture

```
question
   |
   v
+-------+   no tool calls / done   +--------------------+
| agent |------------------------->| final AIMessage,   |
+-------+                          | evidence-checked   |
   |  ^ tool calls chosen          | in run_agent()     |
   v  |  (loop, max 3 rounds)      +--------------------+
+-------+
| tools |
+-------+
```

- **`agent` node** (`app/agent/graph.py`) — a real LLM call (Qwen3:4B via
  Ollama, `.bind_tools(...)`) that decides whether the question needs a
  tool, and if so, which one(s) and with what arguments. This is native
  LLM function-calling, not a keyword classifier — it's the actual
  "understand intent, decide whether tools are required" step.
- **`tools` node** — executes whatever tool calls the model just made
  against the live database, appends the results back into the
  conversation as `ToolMessage`s, and records two things: a `trace`
  entry (tool name, input, output, timestamp — Phase 6 requirement #8)
  and a list of `EvidenceItem`s (structured, citable facts).
- Loop back to `agent`, bounded at `MAX_ITERATIONS = 3` rounds — this is
  what makes multi-step questions work: the model can call
  `check_quality`, see the result, then decide it *also* needs
  `get_lineage`, call that, and only then produce a final answer.
- **`force_answer`** — a safety net. If the model still wants tools after
  3 rounds, one final call is made with tools *unbound* (it physically
  cannot call another one) and a reminder to answer from what's already
  gathered. This guarantees the graph terminates.

## The tool layer (`app/agent/tools.py`)

Eight tools, one per required capability, every one a thin wrapper
around a Phase 4 service function or the Phase 5 `semantic_search` — no
query logic is duplicated:

| Tool | Wraps |
|---|---|
| `search_assets` | `services.assets.search_assets` |
| `get_schema` | `services.assets.get_schema` |
| `get_owner` | `services.assets.get_owner` |
| `check_pii` | `services.assets.get_asset` + `get_schema` (single-asset), or `search_assets(pii_only=True)` (catalog-wide) |
| `get_lineage` | `services.lineage.get_lineage` |
| `check_quality` | `services.quality.check_data_quality` |
| `get_business_definition` | `services.business_terms.get_business_definition` |
| `search_documentation` | `rag.retrieval.semantic_search` (results below similarity 0.35 are dropped as noise) |

Each tool's underlying `_run_*` function returns a `ToolResult(summary, evidence)`:
`summary` is what the LLM reads back as the tool's output; `evidence` is
a list of `EvidenceItem`s the graph accumulates for citations. The
`StructuredTool` objects bound to the LLM (for name/description/schema)
and the actual execution path both call the same `_run_*` function — the
LLM-facing tool is never itself invoked, only used for its schema, so
there's exactly one code path per capability, not two.

`search_assets` gained an `owner` filter in this phase (extending the
Phase 4 service, not duplicating it) specifically so "which PII datasets
does Sales Engineering own" can be answered with one call:
`search_assets(pii_only=True, owner="Sales Engineering")`.

## Grounding is enforced in code, not just prompted

The system prompt tells the model to ground answers only in tool results
and to say so explicitly when it can't find something. A 4B parameter
model won't always follow that perfectly. So `app/agent/run.py` adds a
hard backstop: **if the graph finishes with zero evidence gathered, the
answer is unconditionally replaced** with
`"I could not find information about that in ContextIQ's available data..."` —
regardless of what the model itself said. This is what makes Phase 6
requirement #7 ("must not invent information") a guarantee, not a
request.

## LLM provider: local Qwen3:4B via Ollama

No hosted LLM API key was available in this environment (same situation
as Phase 5's embeddings). After checking hardware (15.7GB RAM, Iris Xe
integrated graphics — meaning CPU-only inference, no usable GPU
acceleration) and researching small tool-calling models, **Qwen3:4B**
was chosen: native tool-calling support across the whole Qwen3 family (no
custom prompt template needed), ~2.5GB download, comfortable RAM
footprint, and enough reliability for genuinely multi-step tool
orchestration — smaller/faster options were flagged in research as
unreliable above one tool call per turn, which this project's example
questions explicitly require.

Provider selection is entirely config-driven (`app/config/settings.py`:
`LLM_PROVIDER`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`), per requirement #9.
`app/agent/llm.py` is the only file that knows a specific provider exists
— swapping to a hosted model later means adding a branch there, nothing
in `graph.py` or `tools.py` changes.

### The `<think>` leakage issue

Qwen3 emits internal reasoning wrapped in `<think>...</think>` tags.
Tested directly against Ollama's raw `/api/chat` endpoint: even with
`"think": false` in the request, a `<think>` block still leaked into the
response's `content` field. Tested separately through `langchain-ollama`'s
`ChatOllama` integration: `content` came back clean in both the
tool-call and final-answer cases — this library version apparently
already separates reasoning from content correctly.

Rather than trust that either implementation detail holds forever,
`app/agent/text.strip_thinking()` is applied to every piece of model
output before it's used for a routing decision or shown to a user —
defense in depth, independent of which code path is actually leaking on
any given day.

## Independent of FastAPI, MCP, and the frontend

`run_agent(question, db=None)` in `app/agent/run.py` is the only public
entrypoint. It takes a plain string and an optional SQLAlchemy session
(creates and closes its own if none is passed) and returns a plain
`AgentResult` dataclass — no FastAPI types, no HTTP concerns. This is
what lets the same function be called directly from tests (as it is in
`backend/tests/test_agent.py`), and later from an API route or the MCP
server, without any adapter code duplicating logic.

## Verification against live Postgres + Ollama

`backend/tests/test_agent.py` — 9 integration tests, each running the
real graph against the live database and the real qwen3:4b model, no
mocks:

```
tests/test_agent.py::test_single_tool_owner_question PASSED
tests/test_agent.py::test_single_tool_business_definition PASSED
tests/test_agent.py::test_pii_question PASSED
tests/test_agent.py::test_lineage_question PASSED
tests/test_agent.py::test_quality_trust_question PASSED
tests/test_agent.py::test_multi_tool_quality_and_lineage PASSED
tests/test_agent.py::test_multi_tool_pii_and_owner PASSED
tests/test_agent.py::test_unanswerable_question PASSED
tests/test_agent.py::test_no_thinking_leakage_in_answer PASSED

9 passed in 1477.32s (0:24:37)
```

Notably: both multi-tool tests passed, confirming the LLM correctly
chose to call two different tools within the loop for compound
questions (`check_quality` + `get_lineage`; the `owner`-filter extension
to `search_assets` for the PII+ownership question). The unanswerable
question ("What is the capital of France?") correctly triggered zero
tool calls and the code-enforced fallback message, not a hallucinated
geography answer. ~2.7 minutes/question average, entirely CPU-bound —
the real cost of this hardware/model choice, discussed above.
