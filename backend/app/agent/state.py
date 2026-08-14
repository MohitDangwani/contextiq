"""LangGraph state and shared data types for the ContextIQ agent."""
from dataclasses import dataclass, field
from typing import Annotated, TypedDict

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


@dataclass
class ToolResult:
    """What a tool implementation returns internally: a summary for the
    LLM to read, plus the structured evidence backing it."""

    summary: str
    evidence: list[EvidenceItem] = field(default_factory=list)


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
