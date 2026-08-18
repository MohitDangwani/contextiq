"""LangGraph state and shared data types for the ContextIQ agent."""
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


@dataclass
class EvidenceItem:
    """One fact a tool returned, carrying its own citation. The agent's
    final answer is only ever grounded in a list of these -- never in
    the LLM's own claims about what it knows."""

    source_type: str  # "asset" | "schema" | "owner" | "pii" | "lineage" | "quality" | "business_term" | "documentation"
    title: str
    asset_id: str | None
    detail: str
    citation: str


@dataclass
class ToolInvocation:
    """One entry in the request trace: what tool was called, with what
    input, and a summary of what it returned. This is what lets a later
    evaluation phase (or a curious developer) see exactly why the agent
    answered the way it did."""

    tool: str
    input: dict
    output_summary: str
    timestamp: str
    evidence_count: int = 0  # how many EvidenceItems THIS specific call produced --
    # 0 means this specific lookup came back empty (not found / no match),
    # a structural signal app.agent.grounding uses to tell "nothing was
    # found for this" apart from "something unrelated was found elsewhere",
    # without re-parsing free text.


@dataclass
class ToolResult:
    """What a tool implementation returns internally: a summary for the
    LLM to read, plus the structured evidence backing it."""

    summary: str
    evidence: list[EvidenceItem] = field(default_factory=list)


def evidence_digest(evidence: list[EvidenceItem]) -> str:
    """Render gathered evidence as a flat, citable list -- the one shared
    formatting used everywhere evidence needs to be handed back to an LLM
    call (force_answer's reminder, the agent's give-up retry, the
    grounding verifier). One definition so all three read the same shape."""
    return "\n".join(f"- {e.detail} (source: {e.citation})" for e in evidence)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    trace: list[ToolInvocation]
    evidence: list[EvidenceItem]
    iterations: int


@dataclass
class SourceRef:
    label: str
    asset_id: str | None
    source_type: str


@dataclass
class AgentResult:
    """What run_agent() returns: the public contract of the agent layer."""

    question: str
    answer: str
    sources: list[SourceRef]
    evidence: list[EvidenceItem]
    trace: list[ToolInvocation]
    # The grounding gate's actual verdict (app.agent.grounding.verify_support),
    # kept instead of discarded after run_agent() decides the answer -- lets
    # callers (the API, the frontend) render supported/partial/abstained
    # state off the real decision instead of re-deriving a weaker proxy
    # (e.g. "evidence is non-empty") that can't distinguish partial from
    # supported. "not_supported" on the zero-evidence hard-backstop path too,
    # since that path is semantically the same outcome (nothing supports
    # an answer), it just never reaches verify_support() to get there.
    #
    # Defaults to "not_supported" (fail-closed, same posture as
    # app.agent.grounding) so existing synthetic-AgentResult call sites
    # (e.g. test_evaluation.py's _result() helper, predating this field)
    # keep working without needing to know about grounding internals --
    # run_agent() itself always sets this explicitly.
    grounding_status: Literal["supported", "partial", "not_supported"] = "not_supported"
