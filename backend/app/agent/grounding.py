"""The grounding gate: the one place that decides whether gathered
evidence actually supports answering a question, before any answer is
accepted.

Why this exists (see docs/agent.md for the full writeup): run.py's only
guarantee used to be "zero evidence -> abstain". That's necessary but not
sufficient -- evidence being non-empty has never meant "evidence that
answers THIS question", only "some tool call produced some EvidenceItem
this turn". A model that gathers real-but-irrelevant evidence (e.g. a
broad exploratory search hit while the targeted lookup came back empty)
could previously have that irrelevant evidence accepted as grounding for
an answer, because nothing ever checked the two against each other.

This module closes that gap with a single, narrow, structured
classification call -- not by adding another rule to the main agent's
already-crowded system prompt. Classifying "does this evidence address
this question" is unavoidably a language-understanding task (there's no
deterministic, non-NLP way to do it), so it stays an LLM call -- but its
output is a constrained verdict (SUPPORTED / PARTIAL / NOT_SUPPORTED,
not free text), and what happens next is decided entirely by code
(app/agent/run.py), not by hoping the model polices itself. If this call
fails to parse or throws, it fails CLOSED (NOT_SUPPORTED) -- the same
"never guess" posture as the rest of the grounding design, applied here
too: a broken classifier can only make the system more cautious, never
less safe.
"""
from dataclasses import dataclass
from typing import Literal

from app.agent.llm import get_chat_model
from app.agent.state import EvidenceItem, ToolInvocation, evidence_digest
from app.agent.text import extract_json_object

SupportStatus = Literal["supported", "partial", "not_supported"]

_SUPPORT_PROMPT = """You are checking whether retrieved evidence actually supports answering a \
question -- not whether the evidence is real, only whether it is ON TOPIC for what was asked.

Question: {question}

Evidence retrieved from ContextIQ's catalog/tools:
{evidence}
{unresolved_section}
Being about the right dataset is NOT enough by itself -- check whether the evidence addresses \
the SPECIFIC ATTRIBUTE OR TOPIC asked about, not just the same entity. Example: a question \
about a dataset's backup/disaster-recovery policy is NOT supported by evidence about that same \
dataset's PII status or quality score -- right entity, wrong topic, still not_supported.

Classify the evidence against the question:
- "supported": the evidence directly addresses what was asked and is enough to answer it.
- "partial": the evidence addresses PART of what was asked, but a specific piece is missing.
- "not_supported": none of the evidence actually addresses what was asked -- it may be real \
data, and even about the right dataset, but about a different attribute/topic than what was \
asked. A specific lookup coming back empty (see "lookups that found nothing" below, if \
present) does not get overridden by unrelated evidence found elsewhere.

Respond with ONLY this JSON, nothing else:
{{"status": "supported" | "partial" | "not_supported", "gap": "<if partial, what's missing, else null>", "reasoning": "<one short sentence>"}}
"""


@dataclass
class SupportVerdict:
    status: SupportStatus
    gap: str | None
    reasoning: str


def _unresolved_section(trace: list[ToolInvocation]) -> str:
    empty_calls = [t for t in trace if t.evidence_count == 0]
    if not empty_calls:
        return ""
    lines = "\n".join(f"- {t.tool}({t.input}): {t.output_summary}" for t in empty_calls)
    return f"\nSpecific lookups that found nothing (still evidence -- absence of a result):\n{lines}\n"


def verify_support(
    question: str, evidence: list[EvidenceItem], trace: list[ToolInvocation]
) -> SupportVerdict:
    prompt = _SUPPORT_PROMPT.format(
        question=question,
        evidence=evidence_digest(evidence),
        unresolved_section=_unresolved_section(trace),
    )
    try:
        model = get_chat_model()
        response = model.invoke(prompt)
        parsed = extract_json_object(response.content if isinstance(response.content, str) else None)
        if parsed is None:
            return SupportVerdict("not_supported", None, "verifier response was unparseable -- failed closed")
        status = parsed.get("status")
        if status not in ("supported", "partial", "not_supported"):
            return SupportVerdict("not_supported", None, f"verifier returned invalid status {status!r} -- failed closed")
        return SupportVerdict(status, parsed.get("gap"), str(parsed.get("reasoning", "")))
    except Exception as exc:  # the verifier is a safety gate -- it must never crash the agent, only fail closed
        return SupportVerdict("not_supported", None, f"verifier call failed ({exc}) -- failed closed")
