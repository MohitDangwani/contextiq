"""Top-level entrypoint for running the ContextIQ agent.

Independent of FastAPI: owns its own DB session unless one is passed in
(tests pass one already open against the live database). This is the
only function other layers (a future API route, MCP, evaluation) should
call -- everything else in app/agent/ is an implementation detail.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.agent.graph import SYSTEM_PROMPT, build_graph
from app.agent.grounding import verify_support
from app.agent.state import AgentResult, EvidenceItem, SourceRef
from app.config.database import SessionLocal

NOT_FOUND_MESSAGE = (
    "I could not find information about that in ContextIQ's available data "
    "(metadata, lineage, quality, business definitions, or documentation)."
)


def _dedupe_sources(evidence: list[EvidenceItem]) -> list[SourceRef]:
    seen: set[tuple[str, str]] = set()
    sources: list[SourceRef] = []
    for item in evidence:
        key = (item.source_type, item.citation)
        if key in seen:
            continue
        seen.add(key)
        sources.append(SourceRef(label=item.citation, asset_id=item.asset_id, source_type=item.source_type))
    return sources


def run_agent(question: str, db: Session | None = None) -> AgentResult:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        graph = build_graph(session)
        initial_state = {
            "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)],
            "question": question,
            "trace": [],
            "evidence": [],
            "iterations": 0,
        }
        final_state = graph.invoke(initial_state, config={"recursion_limit": 25})

        evidence = final_state["evidence"]
        if not evidence:
            # No grounding evidence was gathered at all. Enforced here in
            # code -- not just requested in the system prompt -- because a
            # small local model can't be trusted 100% to follow
            # instructions on every call. This is the hard guarantee
            # behind "the agent must not invent information".
            answer = NOT_FOUND_MESSAGE
            # This path never reaches verify_support() -- there's nothing
            # to classify -- but it's the same outcome ("nothing supports
            # an answer"), so it gets the same label callers act on.
            grounding_status = "not_supported"
        else:
            # Evidence existing is NOT the same as evidence that answers
            # THIS question -- a model that went exploring can gather real,
            # correctly-grounded facts about something else entirely. The
            # grounding gate (app/agent/grounding.py) is a second,
            # code-enforced check: a dedicated classification of whether
            # the gathered evidence actually supports this specific
            # question, separate from the model's own drafted answer, so
            # "some evidence exists" can no longer be silently read as
            # "therefore trust whatever was said".
            last_content = final_state["messages"][-1].content
            draft = last_content if isinstance(last_content, str) and last_content.strip() else ""
            verdict = verify_support(question, evidence, final_state["trace"])
            answer = draft if draft and verdict.status != "not_supported" else NOT_FOUND_MESSAGE
            grounding_status = verdict.status

        return AgentResult(
            question=question,
            answer=answer,
            sources=_dedupe_sources(evidence),
            evidence=evidence,
            trace=final_state["trace"],
            grounding_status=grounding_status,
        )
    finally:
        if owns_session:
            session.close()
