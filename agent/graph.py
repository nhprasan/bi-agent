"""
agent/graph.py

LangGraph agent wiring — two nodes, one loop.

Flow:
    START -> call_llm -> (has tool calls?) -> call_tools -> call_llm -> ...
                      -> (no tool calls)  -> END

Nodes:
    call_llm   — sends messages to Groq, gets back text or tool call requests
    call_tools — runs whatever tools the LLM asked for, feeds results back

All tools take no arguments. The LLM just decides which tool to call,
runs it, reads the full result, and extracts what's relevant to the query.
"""

import json
import time
from typing import Annotated

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from config import GROQ_API_KEY
from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    get_pipeline_summary,
    get_owner_performance,
    get_revenue_summary,
    get_sector_performance,
    get_collections_status,
)


# cap node visits per turn — prevents infinite loops if something goes wrong
RECURSION_LIMIT = 10


# ---------------------------------------------------------------------------
# State
# LangGraph passes this between nodes. add_messages appends rather than replaces.
# tool_trace collects metadata for the UI expander (tool name + timing).
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages:   Annotated[list, add_messages]
    tool_trace: list


# ---------------------------------------------------------------------------
# LLM setup
# Tools are registered here so Groq knows what's available to call.
# ---------------------------------------------------------------------------

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0,
)

TOOLS = [
    get_pipeline_summary,
    get_owner_performance,
    get_revenue_summary,
    get_sector_performance,
    get_collections_status,
]

llm_with_tools = llm.bind_tools(TOOLS)
TOOL_MAP       = {t.name: t for t in TOOLS}


# ---------------------------------------------------------------------------
# History trimming
# Keep only the last N exchanges so we don't blow the context window.
# ---------------------------------------------------------------------------

def _trim_history(chat_history: list, max_exchanges: int = 2) -> list:
    if not chat_history:
        return []
    collected, found = [], 0
    for msg in reversed(chat_history):
        collected.insert(0, msg)
        if isinstance(msg, HumanMessage):
            found += 1
            if found == max_exchanges:
                break
    return collected


# ---------------------------------------------------------------------------
# Node 1 — call_llm
# Passes the message list to Groq. Response is either a final answer
# or a list of tool calls to make.
# ---------------------------------------------------------------------------

def call_llm(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {
        "messages":   [response],
        "tool_trace": state.get("tool_trace", []),
    }


# ---------------------------------------------------------------------------
# Node 2 — call_tools
# Runs each tool the LLM asked for and wraps results in ToolMessages.
# Tools take no arguments, so there's no argument parsing or null handling needed.
# ---------------------------------------------------------------------------

def call_tools(state: AgentState) -> dict:
    last_msg   = state["messages"][-1]
    tool_trace = list(state.get("tool_trace", []))
    new_msgs   = []

    for tool_call in last_msg.tool_calls:
        name    = tool_call["name"]
        tool_fn = TOOL_MAP.get(name)

        if not tool_fn:
            result = json.dumps({"error": f"Tool '{name}' not found."})
            tool_trace.append({"tool_name": name, "duration_ms": 0})
        else:
            start = time.time()
            try:
                result = tool_fn.invoke({})   # no args — always call with empty dict
            except Exception as e:
                result = json.dumps({"error": str(e)})
            tool_trace.append({
                "tool_name":   name,
                "duration_ms": round((time.time() - start) * 1000),
            })

        new_msgs.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

    return {"messages": new_msgs, "tool_trace": tool_trace}


# ---------------------------------------------------------------------------
# Routing — after call_llm, go to tools if needed, else stop.
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> str:
    if state["messages"][-1].tool_calls:
        return "call_tools"
    return END


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

builder = StateGraph(AgentState)
builder.add_node("call_llm",   call_llm)
builder.add_node("call_tools", call_tools)
builder.add_edge(START,        "call_llm")
builder.add_edge("call_tools", "call_llm")
builder.add_conditional_edges("call_llm", should_continue, {"call_tools": "call_tools", END: END})
graph = builder.compile()


# ---------------------------------------------------------------------------
# Entry point — called by app.py on each user message
# ---------------------------------------------------------------------------

def run_agent(user_message: str, chat_history: list) -> dict:
    initial_messages = (
        [SystemMessage(content=SYSTEM_PROMPT)]
        + _trim_history(chat_history, max_exchanges=2)
        + [HumanMessage(content=user_message)]
    )
    final_state = graph.invoke(
        {"messages": initial_messages, "tool_trace": []},
        {"recursion_limit": RECURSION_LIMIT},
    )
    return {
        "answer":     final_state["messages"][-1].content,
        "tool_trace": final_state.get("tool_trace", []),
    }