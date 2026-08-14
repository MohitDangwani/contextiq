"""The ContextIQ agent graph.

    question
       |
       v
    +-------+   no tool calls / enough evidence   +------------------+
    | agent |------------------------------------->|  (end, via the  |
    +-------+                                       |  agent's own   |
       |  ^ tool calls chosen                       |  final message) |
       v  | (loop, bounded by MAX_ITERATIONS)       +------------------+
    +-------+
    | tools |
    +-------+

If the loop hits MAX_ITERATIONS and the model still wants more tools,
`force_answer` makes one final LLM call with tools unbound (so it
physically cannot ask for more) and a reminder to answer from whatever
evidence has been gathered -- this guarantees the graph terminates.

`agent` = understand intent + decide which tool(s) are needed.
`tools` = call them + collect evidence (this is the tracing point).
The final AIMessage's content, once evidence-checked in app/agent/run.py,
becomes the grounded answer.
"""
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.state import AgentState, ToolInvocation
from app.agent.text import strip_thinking
from app.agent.tools import build_tool_specs

# Sized for the observed worst case, not unbounded: some models (Nemotron
# included) issue one tool call per round rather than batching several into
# one AIMessage, and a genuine multi-hop question ("show the lineage from
# customers to the revenue dashboard") needs up to 4 sequential calls
# (2x search_assets to resolve ids + get_lineage). 3 was sized only for the
# single/double-tool cases and left no headroom for that shape of question.
# Still strictly bounded -- see force_answer_node below for what happens if
# even this is exceeded.
MAX_ITERATIONS = 4

SYSTEM_PROMPT = """You are ContextIQ, an AI agent that answers questions about Brightcart's \
enterprise data catalog: datasets, schemas, ownership, PII, lineage, data quality, business \
term definitions, and documentation.

Rules:
- Only call a tool if the question actually needs it. Do not call tools for greetings or \
questions unrelated to Brightcart's data catalog.
- A question may need MORE THAN ONE tool. For example "is X trustworthy and where does its \
data come from?" needs both check_quality AND get_lineage -- call all the tools you need \
before answering.
- Ground your final answer ONLY in what the tools returned. Never use outside/pretrained \
knowledge to fill a gap -- if a tool didn't return it, it isn't evidence and it doesn't \
belong in the answer.
- If a tool result says something doesn't exist, that's your answer -- don't guess instead.
- Before answering, check that what the tools returned actually addresses what was asked. If \
none of it does, that's the same as not finding it -- say so, don't report unrelated facts \
as if they were the answer. Example: asked for a dataset's SLA/uptime guarantee but the \
tools only returned its schema or owner? That doesn't answer the question -- abstain rather \
than substituting whatever unrelated facts you did find.
- If, after checking the relevant tools, you cannot find the information, say so explicitly \
(e.g. "I don't have enough information in the ContextIQ catalog to answer that") instead of \
guessing.
- If only part of the question is answered by the tools, answer that part and clearly say \
what's missing, instead of inventing it.
- When you have enough information, respond with a direct, concise final answer and stop \
calling tools.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_incomplete(content) -> bool:
    """True for empty content, and for a bare stub header (e.g. "Final
    Answer:") with nothing after it -- both signs the model stopped before
    writing the actual answer rather than genuinely having nothing to say."""
    if not isinstance(content, str):
        return not content
    text = content.strip()
    return not text or (text.endswith(":") and len(text) < 30)


def build_graph(db: Session):
    tool_specs = build_tool_specs(db)
    tools_list = [spec.tool for spec in tool_specs.values()]
    llm_with_tools = get_chat_model(bind_tools_list=tools_list)
    llm_plain = get_chat_model()

    def agent_node(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        if isinstance(response.content, str):
            response.content = strip_thinking(response.content)

        # A small model occasionally spends a whole turn on hidden reasoning
        # and stops without ever emitting real final-answer text --
        # finish_reason "stop", no tool_calls, and content that's either
        # empty or just a stub header like "Final Answer:". Not a
        # token-budget problem (plenty of the max_tokens budget is often
        # left unused): the model just ends the turn incomplete. Left as
        # is, this would silently discard evidence already gathered, since
        # run.py treats empty/near-empty content the same as "nothing to
        # say". Bounded retries (2 max) with an explicit nudge recover this
        # in practice without risking an unbounded loop.
        attempts = 0
        while not response.tool_calls and _looks_incomplete(response.content) and attempts < 2:
            nudge = SystemMessage(content="Provide your final answer now, in plain text.")
            response = llm_with_tools.invoke(state["messages"] + [nudge])
            if isinstance(response.content, str):
                response.content = strip_thinking(response.content)
            attempts += 1

        return {"messages": [response]}

    def tools_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        new_messages = []
        new_trace = list(state["trace"])
        new_evidence = list(state["evidence"])

        for call in last.tool_calls:
            name = call["name"]
            args = call.get("args") or {}
            spec = tool_specs.get(name)
            if spec is None:
                result_summary = f"Unknown tool '{name}'."
                evidence = []
            else:
                try:
                    result = spec.run(**args)
                    result_summary = result.summary
                    evidence = result.evidence
                except Exception as exc:  # a failing tool becomes visible, evidence-free output -- not a crash
                    result_summary = f"Tool '{name}' failed: {exc}"
                    evidence = []

            new_messages.append(ToolMessage(content=result_summary, tool_call_id=call["id"]))
            new_trace.append(ToolInvocation(
                tool=name, input=args, output_summary=result_summary[:300], timestamp=_now(),
            ))
            new_evidence.extend(evidence)

        return {
            "messages": new_messages,
            "trace": new_trace,
            "evidence": new_evidence,
            "iterations": state["iterations"] + 1,
        }

    def force_answer_node(state: AgentState) -> dict:
        messages = list(state["messages"])

        # If the limit was hit exactly as the model requested another round,
        # the last message is an AIMessage with tool_calls that tools_node
        # never got to execute. Left dangling (a tool request with no
        # matching ToolMessage), that malformed conversation shape is what
        # was making a small model conclude nothing had been found at all --
        # including forgetting the evidence earlier rounds already gathered.
        # Close it out explicitly so the transcript stays well-formed.
        last = messages[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            for call in last.tool_calls:
                messages.append(ToolMessage(
                    content="Not executed: the tool-call limit was reached before this request ran.",
                    tool_call_id=call["id"],
                ))

        # Hand the model a code-built digest of what's actually been
        # gathered, rather than relying on it to re-derive that itself from
        # a long, mixed transcript of ToolMessages -- this is what lets the
        # final answer actually use evidence retrieved in earlier rounds
        # instead of defaulting to "no evidence available".
        if state["evidence"]:
            digest = "\n".join(f"- {e.detail} (source: {e.citation})" for e in state["evidence"])
            reminder = SystemMessage(
                content="You have reached the tool-call limit. The evidence below was already "
                "retrieved from ContextIQ in earlier steps -- answer the question using ONLY "
                "this evidence, and do not request any more tools:\n\n" + digest
            )
        else:
            reminder = SystemMessage(
                content="You have reached the tool-call limit and no evidence was retrieved. "
                "State clearly that you could not find the requested information in "
                "ContextIQ's catalog. Do not request any more tools and do not guess."
            )

        response = llm_plain.invoke(messages + [reminder])
        cleaned = strip_thinking(response.content) if isinstance(response.content, str) else ""
        response.content = cleaned or "I was unable to gather enough information to answer this question."
        return {"messages": [response]}

    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        has_calls = isinstance(last, AIMessage) and bool(last.tool_calls)
        if not has_calls:
            return "end"
        if state["iterations"] >= MAX_ITERATIONS:
            return "force_answer"
        return "tools"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("force_answer", force_answer_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", route_after_agent, {"tools": "tools", "force_answer": "force_answer", "end": END}
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("force_answer", END)

    return graph.compile()
