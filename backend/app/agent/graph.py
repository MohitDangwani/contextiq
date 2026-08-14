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

MAX_ITERATIONS = 3

SYSTEM_PROMPT = """You are ContextIQ, an AI agent that answers questions about Brightcart's \
enterprise data catalog: datasets, schemas, ownership, PII, lineage, data quality, business \
term definitions, and documentation.

Rules:
- Only call a tool if the question actually needs it. Do not call tools for greetings or \
questions unrelated to Brightcart's data catalog.
- A question may need MORE THAN ONE tool. For example "is X trustworthy and where does its \
data come from?" needs both check_quality AND get_lineage -- call all the tools you need \
before answering.
- Ground your final answer ONLY in what the tools returned. Never state a fact that no tool \
result supports.
- If, after checking the relevant tools, you cannot find the information, say so explicitly \
(e.g. "I could not find information about X in ContextIQ's data") instead of guessing.
- When you have enough information, respond with a direct, concise final answer and stop \
calling tools.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_graph(db: Session):
    tool_specs = build_tool_specs(db)
    tools_list = [spec.tool for spec in tool_specs.values()]
    llm_with_tools = get_chat_model(bind_tools_list=tools_list)
    llm_plain = get_chat_model()

    def agent_node(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        if isinstance(response.content, str):
            response.content = strip_thinking(response.content)
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
        reminder = SystemMessage(
            content="You have reached the tool-call limit. Answer now, using only the "
            "evidence already gathered. Do not request any more tools."
        )
        response = llm_plain.invoke(state["messages"] + [reminder])
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
