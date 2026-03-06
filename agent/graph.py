"""
agent/graph.py

BI agent built with LangGraph.

Graph structure:
    START --> call_llm --> should_continue? --> call_tools --> call_llm (loop)
                                          --> END (if no tool calls)

Nodes:
    call_llm   - sends messages to Groq and gets back a response
    call_tools - executes whatever tools the LLM asked for

Edges:
    call_llm --> call_tools   (if LLM response has tool calls)
    call_llm --> END          (if LLM response has no tool calls — final answer)
    call_tools --> call_llm   (always loop back after tools run)
"""

import json
import time
from typing import Annotated

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
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


# max number of nodes LangGraph can visit in one run
# with 6 tools, 10 is more than enough — prevents infinite loops
RECURSION_LIMIT = 10


# ---------------------------------------------------------------------------
# State
# LangGraph passes this dict between nodes on every step.
# add_messages is a reducer — it appends new messages instead of replacing.
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages:   Annotated[list, add_messages]
    tool_trace: list   # accumulates tool call metadata for the UI


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0,
)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@tool
def tool_get_pipeline_summary() -> str:
    """
    Use this tool to answer questions about the sales pipeline.
    Covers: total pipeline value, deal counts by status and stage,
    open deals by sector and by owner/BD rep, won deal value.
    Example questions: 'What is our pipeline?', 'How many open deals do we have?',
    'Which sector has the most pipeline?', 'What is the total won value?'
    """
    return json.dumps(get_pipeline_summary(), default=str)


@tool
def tool_get_owner_performance() -> str:
    """
    Use this tool to answer questions about individual BD/sales owner performance.
    Covers: win rate, loss rate, deal counts, won value, open pipeline per owner.
    Example questions: 'Who is the best performing BD?', 'What is the win rate per owner?',
    'Which owner has the most open deals?'
    """
    return json.dumps(get_owner_performance(), default=str)


@tool
def tool_get_revenue_summary() -> str:
    """
    Use this tool to answer questions about overall revenue and financials.
    Covers: total contracted value, billed amount, collected amount,
    unbilled amount, receivables, billing and invoice status breakdowns.
    Example questions: 'What is our total revenue?', 'How much have we billed?',
    'How much is still unbilled?', 'What is our total contracted value?'
    """
    return json.dumps(get_revenue_summary(), default=str)


@tool
def tool_get_sector_performance() -> str:
    """
    Use this tool to answer questions about performance broken down by industry sector.
    Covers: work order count, contracted value, billed, collected and receivable
    per sector, execution status breakdown per sector.
    Example questions: 'Which sector generates the most revenue?',
    'How is mining performing?', 'Compare sectors by billed value.'
    """
    return json.dumps(get_sector_performance(), default=str)


@tool
def tool_get_collections_status() -> str:
    """
    Use this tool to answer questions about outstanding payments and collections.
    Covers: total receivables, accounts with outstanding amounts, priority AR accounts,
    stuck or paused work orders, WO open vs closed status.
    Example questions: 'How much money is outstanding?', 'Which clients owe us money?',
    'What are our priority collection accounts?', 'Are there any stuck work orders?'
    """
    return json.dumps(get_collections_status(), default=str)


TOOLS = [
    tool_get_pipeline_summary,
    tool_get_owner_performance,
    tool_get_revenue_summary,
    tool_get_sector_performance,
    tool_get_collections_status,
]

llm_with_tools = llm.bind_tools(TOOLS)
TOOL_MAP       = {t.name: t for t in TOOLS}


# ---------------------------------------------------------------------------
# History trimming — keep last N human+AI exchanges to stay within token limits
# ---------------------------------------------------------------------------

def _trim_history(chat_history: list, max_exchanges: int = 2) -> list:
    if not chat_history:
        return []

    collected       = []
    exchanges_found = 0

    for msg in reversed(chat_history):
        collected.insert(0, msg)
        if isinstance(msg, HumanMessage):
            exchanges_found += 1
            if exchanges_found == max_exchanges:
                break

    return collected


# ---------------------------------------------------------------------------
# Node 1: call_llm
# Sends the current message list to Groq and appends the response to state.
# ---------------------------------------------------------------------------

def call_llm(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {
        "messages":   [response],
        "tool_trace": state.get("tool_trace", []),
    }


# ---------------------------------------------------------------------------
# Node 2: call_tools
# Runs every tool the LLM asked for and appends ToolMessages back to state.
# Records timing info into tool_trace for the UI expander.
# ---------------------------------------------------------------------------

def call_tools(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    tool_trace   = list(state.get("tool_trace", []))
    new_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_fn   = TOOL_MAP.get(tool_name)

        if not tool_fn:
            result = json.dumps({"error": f"Tool '{tool_name}' not found."})
            tool_trace.append({
                "tool_name":   tool_name,
                "inputs":      tool_call["args"],
                "duration_ms": 0,
            })
        else:
            start = time.time()
            try:
                result = tool_fn.invoke(tool_call["args"])
            except Exception as e:
                result = json.dumps({"error": str(e)})
            duration_ms = round((time.time() - start) * 1000)
            tool_trace.append({
                "tool_name":   tool_name,
                "inputs":      tool_call["args"],
                "duration_ms": duration_ms,
            })

        new_messages.append(
            ToolMessage(content=result, tool_call_id=tool_call["id"])
        )

    return {
        "messages":   new_messages,
        "tool_trace": tool_trace,
    }


# ---------------------------------------------------------------------------
# Conditional edge: should_continue
# Runs after call_llm. Routes to call_tools if there are tool calls,
# otherwise routes to END — that means the LLM has its final answer.
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> str:
    if state["messages"][-1].tool_calls:
        return "call_tools"
    return END


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

builder = StateGraph(AgentState)

# register nodes
builder.add_node("call_llm",   call_llm)
builder.add_node("call_tools", call_tools)

# fixed edges
builder.add_edge(START,        "call_llm")
builder.add_edge("call_tools", "call_llm")  # after tools always go back to LLM

# conditional edge after LLM — either call tools or finish
builder.add_conditional_edges(
    "call_llm",
    should_continue,
    {"call_tools": "call_tools", END: END},
)

graph = builder.compile()


# ---------------------------------------------------------------------------
# Public entry point called by app.py
# ---------------------------------------------------------------------------

def run_agent(user_message: str, chat_history: list) -> dict:
    """
    Run one turn of the agent.

    Builds the initial state with system prompt + trimmed history + new message,
    runs the graph, and returns the final answer + tool trace.
    """
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