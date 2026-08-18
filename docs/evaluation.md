# Evaluation

## What this measures

Every earlier phase's tests (`test_agent.py`, `test_agent_tools.py`) are
hand-written integration tests: a fixed list of specific questions with
specific asserted behaviors, run every time as a pass/fail regression
suite. Phase 10 is different in kind, not just size: a **benchmark** —
a broader, categorized question set with a machine-checkable reference
per question, scored two ways (deterministic metrics and an LLM judge),
producing a report you can compare run over run as the agent, prompt, or
model changes. The Phase 6/8 suites answer "did I break something I
already knew to test for"; this answers "how good is the agent, overall,
right now, on a representative slice of what it's supposed to do."

## Architecture

```
data/evaluation/benchmark.yaml        30 questions, categorized, with
                                       expected_answer / expected_evidence_
                                       asset_ids / expected_tools_any_of /
                                       should_abstain -- all checked
                                       directly against the live seeded
                                       DB, nothing invented
        |
        v
app/evaluation/benchmark.py           load_benchmark(limit=N)
        |
        v
app/evaluation/runner.py              run_evaluation(): for each question,
                                       calls the REAL app.agent.run.run_agent()
                                       -- no mocks -- then scores it
        |                 |
        v                 v
deterministic.py      judge.py
(no LLM call)          (LLM-as-judge, optional via --judge)
        |                 |
        v                 v
        schema.py: QuestionResult, EvaluationSummary
                    |
                    v
        scripts/run_evaluation.py: CLI, prints report, writes JSON
        to data/evaluation/results/ (gitignored -- results are run
        artifacts, not source)
```

Kept deliberately separate from the agent itself: `app/evaluation/` only
*calls* `run_agent()` and reads its `AgentResult` — it never touches
`app/agent/graph.py`, `tools.py`, or the grounding guardrail in `run.py`.
The same separation Phase 4/8 established (context services vs. the
agent that calls them) applies here too: evaluation is a consumer, not
part of the production path.

## The benchmark (`data/evaluation/benchmark.yaml`)

30 questions across the categories the agent is actually meant to
handle: `known_factual` (ownership lookups), `multi_tool` (compound
questions needing 2+ tools), `lineage` (including one `lineage_multi_hop`
case — the same shape as the Phase 6.1 fix), `quality`, `pii`,
`business_definition`, `tool_use_schema`, `documentation`, and four
abstention variants (`abstention_unknown_dataset`,
`abstention_unknown_metric`, `abstention_out_of_domain`,
`abstention_unknown_documentation`, `abstention_partial_evidence`).
Ordered so the first 8 questions (`--limit 8`) already span 8 different
categories, making the smoke-test subset representative rather than
front-loaded with easy cases.

Every `expected_answer`, `expected_evidence_asset_ids`, and
`expected_tools_any_of` value was checked directly against the live
Postgres database (real owners, PII flags, quality-check verdicts,
lineage edges, business term definitions) before being written down —
never invented, and never drawn from outside/general knowledge, per the
same grounding standard the agent itself is held to. A wrong "expected"
value would silently make the benchmark measure the wrong thing.

## Deterministic metrics (`app/evaluation/deterministic.py`)

No LLM call — fast, free, and exactly reproducible for the same agent
output. A floor, not a replacement for the judge below: a keyword or
asset-id match is a weak proxy for "actually correct."

| Metric | What it checks | `None` means |
|---|---|---|
| `tool_choice_correct` | Did the agent call at least one of the question's `expected_tools_any_of`? | Not applicable (abstention question, or question has no specific expected tool) |
| `evidence_overlap` | Fraction of `expected_evidence_asset_ids` actually present in the agent's own evidence | No asset-based expected evidence for this question (e.g. a business-definition question) |
| `abstention_correct` | For `should_abstain=true`: did it actually abstain? For `should_abstain=false`: did it NOT abstain? | (always computed) |
| `keyword_hit` | Fraction of `expected_answer`'s significant words found in the actual answer | (always computed; 1.0 for abstention questions with no comparable answer text) |
| `think_leak` | Did `<think>`/`</think>` leak into the user-facing answer? | (always computed) |
| `latency_s` | Wall-clock time for that question's `run_agent()` call | (always computed) |

`tool_choice_correct` and `evidence_overlap` are intentionally not
scored for abstention questions: earlier testing (Phase 6.1) showed the
agent's own reasonable exploratory tool calls sometimes gather stray
evidence even when it correctly ends up abstaining — penalizing that
would measure the wrong thing.

## LLM judge (`app/evaluation/judge.py`)

Two separate, focused judge calls per question (only when `--judge` is
passed), using the same provider-agnostic `app.agent.llm.get_chat_model()`
the agent itself uses — no separate judge model, no new dependency:

- **Correctness** compares the answer to the benchmark's
  `expected_answer` (the gold reference). "Did it get the right facts."
- **Groundedness** compares the answer to the agent's OWN retrieved
  evidence (`result.evidence`) — a different reference on purpose. "Did
  it only say things its own tool calls actually support." A
  correct-but-ungrounded answer (right by luck, not by evidence) and a
  grounded-but-incorrect answer (evidence existed but was misread) are
  different failure modes worth telling apart, not collapsed into one
  score.

Each is scored 0/1/2 (wrong or fabricated / partially right or one
unsupported detail / fully correct or fully grounded), with the judge
required to return JSON only (`{"score": ..., "reasoning": ...}`),
parsed defensively — an unparseable judge response records `score: None`
and a diagnostic reasoning string rather than crashing the whole run,
consistent with the rest of this project's stance that one failure
shouldn't take down the whole answer/evaluation.

## Running it

```
python scripts/run_evaluation.py                    # full 30 questions, deterministic only
python scripts/run_evaluation.py --limit 8           # first 8, deterministic only
python scripts/run_evaluation.py --limit 8 --judge   # first 8 + LLM judge (~2x runtime: 2 extra LLM calls/question)
```

Results are written to `data/evaluation/results/eval_<UTC timestamp>.json`
(gitignored — these are run artifacts, reproducible from the benchmark
and whatever model/provider was configured at run time, not source).

See `docs/progress.md` for the first `--limit 8 --judge` run's actual
results.
