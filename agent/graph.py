"""
LangGraph ReAct agent that connects Gemini with Monday.com tools and drives
the BI conversation. Returns both the final answer and a tool
trace so app.py can show what the agent did.
"""

import json
import time
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    fetch_deals,
    fetch_work_orders,
    get_cross_board_summary,
    get_pipeline_summary,
    get_revenue_summary,
)
# from config import GEMINI_API_KEY
from config import GROQ_API_KEY


# ---------------------------------------------------------------------------
# 1. Tool Wrappers
# ---------------------------------------------------------------------------
# These wrappers expose only clean, well-documented interfaces to Gemini.
# We return JSON strings because tool outputs must be serializable.


@tool
def tool_get_pipeline_summary(sector: str = "") -> str:
    """Get pipeline overview grouped by sector and stage."""
    result = get_pipeline_summary(sector=sector or None)
    return json.dumps(result, default=str)


@tool
def tool_get_revenue_summary(sector: str = "") -> str:
    """Get revenue, billing and collection aggregates."""
    result = get_revenue_summary(sector=sector or None)
    return json.dumps(result, default=str)


@tool
def tool_get_cross_board_summary() -> str:
    """Compare pipeline vs execution across sectors."""
    result = get_cross_board_summary()
    return json.dumps(result, default=str)


@tool
def tool_fetch_deals(sector: str = "", status: str = "", stage: str = "") -> str:
    """Fetch deal-level records with optional filters."""
    results = fetch_deals(
        sector=sector or None,
        status=status or None,
        stage=stage or None,
    )

    # Limit raw records to avoid blowing up token usage
    summary = {
        "total_returned": len(results),
        "records": results[:10],
    }

    return json.dumps(summary, default=str)


@tool
def tool_fetch_work_orders(
    sector: str = "",
    execution_status: str = "",
    billing_status: str = "",
) -> str:
    """Fetch work-order-level records with optional filters."""
    results = fetch_work_orders(
        sector=sector or None,
        execution_status=execution_status or None,
        billing_status=billing_status or None,
    )

    summary = {
        "total_returned": len(results),
        "records": results[:10],
    }

    return json.dumps(summary, default=str)


ALL_TOOLS = [
    tool_get_pipeline_summary,
    tool_get_revenue_summary,
    tool_get_cross_board_summary,
    tool_fetch_deals,
    tool_fetch_work_orders,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}


# ---------------------------------------------------------------------------
# 2. Agent State
# ---------------------------------------------------------------------------
# messages -> conversation history
# tool_trace -> what tools were executed (for UI panel)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_trace: list[dict]


# ---------------------------------------------------------------------------
# 3. Build LLM (single instance reused)
# ---------------------------------------------------------------------------

# LLM = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash",
#     google_api_key=GEMINI_API_KEY,
#     temperature=0.2,
#     max_tokens=2048,
# ).bind_tools(ALL_TOOLS)

LLM = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=2048,
).bind_tools(ALL_TOOLS, tool_choice="auto")


# ---------------------------------------------------------------------------
# 4. Graph Nodes
# ---------------------------------------------------------------------------


def agent_node(state: AgentState) -> AgentState:
    """
    Calls Gemini with system prompt + conversation history.
    Gemini may return:
        - final text answer
        - tool calls
    """
    time.sleep(2)  # spreads requests across time
    messages_with_system = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    response: AIMessage = LLM.invoke(messages_with_system)

    return {
        "messages": [response],
        "tool_trace": state.get("tool_trace", []),
    }


def tools_node(state: AgentState) -> AgentState:
    """
    Executes requested tools and sends results back to the LLM.
    Also records simple execution trace.
    """

    last_message: AIMessage = state["messages"][-1]
    tool_calls = last_message.tool_calls or []

    tool_messages = []
    trace = list(state.get("tool_trace", []))

    for call in tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        tool_fn = TOOL_MAP.get(tool_name)

        start = time.time()

        if tool_fn is None:
            output = json.dumps({"error": f"Unknown tool: {tool_name}"})
        else:
            try:
                output = tool_fn.invoke(tool_args)
            except Exception as e:
                output = json.dumps({"error": str(e)})

        duration_ms = round((time.time() - start) * 1000)

        trace.append({
            "tool_name": tool_name,
            "inputs": tool_args,
            "duration_ms": duration_ms,
        })

        tool_messages.append(
            ToolMessage(
                content=output,
                tool_call_id=call["id"],
                name=tool_name,
            )
        )

    return {
        "messages": tool_messages,
        "tool_trace": trace,
    }


# ---------------------------------------------------------------------------
# 5. Routing Logic
# ---------------------------------------------------------------------------


def should_continue(state: AgentState) -> str:
    """
    If the LLM requested tools → go to tools node.
    Otherwise → end the loop.
    """
    last = state["messages"][-1]

    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"

    return "end"


# ---------------------------------------------------------------------------
# 6. Build Graph
# ---------------------------------------------------------------------------

def _build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )

    graph.add_edge("tools", "agent")

    return graph.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# 7. Public function used by app.py
# ---------------------------------------------------------------------------

def run_agent(user_message: str, chat_history: list[BaseMessage]) -> dict:
    """
    Main entry point.

    app.py sends:
        - latest user message
        - full chat history

    Returns:
        {
            "answer": str,
            "tool_trace": list
        }
    """

    initial_state: AgentState = {
        "messages": chat_history + [HumanMessage(content=user_message)],
        "tool_trace": [],
    }

    final_state = _GRAPH.invoke(
        initial_state,
        config={"recursion_limit": 9},  # prevents runaway tool loops
    )

    last_message = final_state["messages"][-1]

    content = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    if isinstance(content, list):
        answer = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        answer = str(content).strip()

    return {
        "answer": answer,
        "tool_trace": final_state.get("tool_trace", []),
    }