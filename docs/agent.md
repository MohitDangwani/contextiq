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
   v  |  (loop, max 4 rounds)      +--------------------+
+-------+
| tools |
+-------+
```

- **`agent` node** (`app/agent/graph.py`) — a real LLM call
  (`.bind_tools(...)`, provider-agnostic — see "LLM provider" below) that
  decides whether the question needs a tool, and if so, which one(s) and
  with what arguments. This is native LLM function-calling, not a keyword
  classifier — it's the actual "understand intent, decide whether tools
  are required" step. It also carries a small, bounded (max 2) retry: if
  a turn ends with empty or stub-only content (e.g. `"Final Answer:"`)
  and no tool calls, one retry with an explicit nudge recovers it —
  see "Multi-hop lineage fix" below for why this exists.
- **`tools` node** — executes whatever tool calls the model just made
  against the live database, appends the results back into the
  conversation as `ToolMessage`s, and records two things: a `trace`
  entry (tool name, input, output, timestamp — Phase 6 requirement #8)
  and a list of `EvidenceItem`s (structured, citable facts).
- Loop back to `agent`, bounded at `MAX_ITERATIONS = 4` rounds — this is
  what makes multi-step questions work: the model can call
  `check_quality`, see the result, then decide it *also* needs
  `get_lineage`, call that, and only then produce a final answer.
- **`force_answer`** — a safety net. If the model still wants tools after
  4 rounds, one final call is made with tools *unbound* (it physically
  cannot call another one) and a reminder — now including a code-built
  digest of the evidence already gathered — to answer from that. This
  guarantees the graph terminates. See "Multi-hop lineage fix" below.

## Multi-hop lineage fix (Phase 6.1)

**The bug**: "Show the lineage from customers to the revenue dashboard"
needs up to 4 sequential tool calls (Nemotron tends to issue one call per
round rather than batching several into one `AIMessage`: 2x
`search_assets` to resolve ids + `get_lineage`). With the original
`MAX_ITERATIONS = 3`, the model's 4th tool-call attempt was never
executed — `route_after_agent` routed straight to `force_answer` instead,
leaving a dangling `AIMessage` with unresolved `tool_calls` in the
transcript (no matching `ToolMessage` ever followed it). Handed that
malformed conversation plus a generic "answer from what's gathered"
reminder, the model concluded nothing had been found at all and answered
"I'm unable to provide an answer because there is no relevant evidence
available" — despite 3 rounds of real lineage data from Postgres already
sitting in `state["evidence"]`.

**The fix** (`force_answer_node`, `app/agent/graph.py`), two parts:
1. Any dangling `tool_calls` from the message that triggered the limit
   are closed out with an explicit `ToolMessage` ("Not executed: the
   tool-call limit was reached before this request ran.") so the model
   sees a well-formed transcript, not a request that silently vanished.
2. The reminder now includes a **code-built digest** of
   `state["evidence"]` — every fact already gathered, spelled out
   directly — instead of asking the model to re-derive that from a long,
   mixed transcript of `ToolMessage`s. This is the actual fix: the final
   answer must be able to use evidence already retrieved, and handing it
   over explicitly is far more reliable than hoping a 4B model recalls it.

**Why 4 and not unbounded**: `MAX_ITERATIONS` went from 3 to 4 — a
reasoned, still-strictly-bounded increase sized to the observed worst
case in this project's example questions, not a blind bump. The graph
still terminates in the same way (`force_answer`) if a question somehow
needs more; the digest fix above means even that path now answers
correctly from whatever was gathered, rather than defaulting to "no
evidence".

## Grounded abstention (Phase 6.1)

ContextIQ must answer only from retrieved evidence, never from the
model's own pretrained knowledge — a general-purpose chatbot answering
"what's the weather in Mumbai?" is a failure mode, not a feature.

**The hard backstop** (unchanged, `app/agent/run.py`): if the graph
finishes with zero evidence gathered, the answer is unconditionally
replaced with `NOT_FOUND_MESSAGE`, regardless of what the model itself
said. This is still a code-level guarantee, not a prompt — see
"Grounding is enforced in code, not just prompted" above.

**The gap that backstop doesn't close**: a question can end with
*some* evidence in state that has nothing to do with what was actually
asked — e.g. asking about a disaster-recovery policy that doesn't exist,
where `search_documentation` correctly finds nothing but a follow-up
`search_assets` call incidentally returns real (if irrelevant) metadata
about the dataset in question. The zero-evidence check doesn't fire
(evidence isn't empty), and early testing showed the model would
sometimes report that unrelated data as if it answered the question.

**The fix**: `SYSTEM_PROMPT` gained explicit rules — no outside/pretrained
knowledge as a substitute for missing evidence, treat a tool's "doesn't
exist" result as the answer rather than a cue to guess, name what's
missing instead of inventing it for partial-evidence questions, and check
that gathered evidence actually addresses what was asked before using it.
Tuned iteratively against the live model: an earlier, longer version of
these rules (a rigid "Known: / Unavailable:" template, spelled-out
examples matching the actual test questions) caused a *different* failure
— the model's final turn degenerating into a bare `"Final Answer:"` stub
or the non-sequitur `"No question was provided."` — fixed by trimming the
prompt back down, not by adding more instructions on top. Small models
lose reliability under compound instructions; the shipped version is the
shortest phrasing found that still passes every abstention test.

Examples of what this produces:

| Question | Behavior |
|---|---|
| "Who owns the orders dataset?" | Answered directly from real catalog evidence. |
| "What is the owner of the employee_attrition dataset?" | Explicit abstention — no such dataset exists. |
| "What is the company's employee attrition rate?" | Explicit abstention — not tracked in ContextIQ. |
| "What is the weather in Mumbai?" | Explicit abstention — out of domain, zero tool calls. |
| "What is the owner of the orders dataset, and its GDPR retention period?" | Owner answered from evidence; GDPR retention explicitly named as unavailable, not invented. |

**What this doesn't do**: there's no separate relevance-scoring layer
that inspects gathered evidence for topical fit to the question — that
would be a meaningfully bigger, more fragile piece of machinery (fuzzy
matching or another LLM call) for a project instruction that explicitly
ruled out unnecessary complexity and a rule-based chatbot layer. The two
guarantees that do exist — the hard zero-evidence code backstop, and the
prompt rules above — were verified empirically against all 7 new
regression tests (multiple stable repeated runs, not a single lucky
pass), which is the honest scope of the current guarantee. See
`docs/progress.md` Phase 6.1 for the full test history, including the
failure modes discovered and fixed along the way.

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

## Phase 6.1 verification: LM Studio + Nemotron 3 Nano 4B

The agent also runs against LM Studio's OpenAI-compatible local server
(`LLM_PROVIDER=lmstudio`; see `app/agent/llm.py` and
`app/config/settings.py` — a config change, not a code change, per the
provider-agnostic design above), serving `nvidia/nemotron-3-nano-4b`
GPU-accelerated on an RTX 5060 Laptop GPU. This was the configuration
used to develop and test the Phase 6.1 lineage and grounded-abstention
fixes described above.

```
tests/test_agent.py ......................... 16/16 passed
tests/test_agent_tools.py .................... 27/27 passed
Total: 43/43 passed
```

Confirmed stable across repeated full-suite runs against live Postgres +
live LM Studio, not a single lucky pass. Real tool calls, real GPU
inference (~85-90% utilization during generation, ~4.3-4.5GB VRAM),
average end-to-end response time in the single-digit seconds per
question — an order of magnitude faster than the CPU-only Ollama/Qwen3
path above. Ollama/Qwen3 remains available and unmodified as the
config-selected fallback (`LLM_PROVIDER=ollama`, still the default).
