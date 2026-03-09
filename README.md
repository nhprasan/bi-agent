---
title: BI Agent
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.32.0"
app_file: app.py
pinned: false
---

# 📊 BI Agent — Business Intelligence Assistant

A conversational AI agent that connects to live Monday.com data and answers business intelligence questions for founders and senior executives — covering sales pipeline, revenue, collections, and sector performance.

---

## Overview

BI Agent is a LangGraph-powered ReAct agent with a Streamlit frontend. It reads from two Monday.com boards (Deal Funnel and Work Orders) via GraphQL, normalizes the data, and lets executives ask natural-language questions and get sharp, data-backed answers in seconds.

---

## Features

- **Conversational BI** — Ask questions in plain English about pipeline, revenue, collections, and more
- **Live data** — Pulls fresh data from Monday.com on every query (no stale snapshots)
- **ReAct reasoning** — The agent reasons about which tool to call, calls it, then analyses the result
- **Tool tracing** — Every agent action is logged and visible in the UI expander
- **Data quality reporting** — Every response flags missing or incomplete data with impact ratings
- **Multi-turn memory** — Maintains conversation history across turns (last 2 exchanges)

---

## Architecture

```
User (Streamlit UI)
        │
        ▼
   run_agent()          ← graph.py entry point
        │
        ▼
  ┌─────────────┐
  │  call_llm   │  ◄──────────────────────┐
  └──────┬──────┘                         │
         │ tool_calls?                    │
    Yes  ▼          No                   │
  ┌─────────────┐   ──► END (answer)     │
  │ call_tools  │                         │
  └──────┬──────┘                         │
         └────────────────────────────────┘
```

**Stack:**
- **LLM:** Llama 3.3 70B via Groq
- **Agent framework:** LangGraph + LangChain
- **Frontend:** Streamlit
- **Data source:** Monday.com GraphQL API
- **Data processing:** Pandas

---

## Project Structure

```
.
├── app.py                  # Streamlit UI — chat interface and session state
├── config.py               # Board IDs, column maps, sector canonicalization
├── requirements.txt
├── .gitignore              # Excludes .env and other sensitive/generated files
├── .env                    # API keys (not committed — excluded by .gitignore)
│
└── agent/
    ├── __init__.py
    ├── graph.py            # LangGraph agent — nodes, edges, run_agent()
    ├── tools.py            # Tool functions that query and aggregate Monday.com data
    ├── normalizer.py       # Cleans and normalizes raw Monday.com API responses
    └── prompts.py          # System prompt (ReAct instructions for the LLM)
```

---

## Data Sources

| Board | What it covers |
|---|---|
| **Deal Funnel** | All deals — open, won, dead, on hold. Deal value, sector, BD owner assignments, dead deal value lost. |
| **Work Orders** | All contracted work. Contracted value, billed, collected, unbilled, receivables. Execution status, invoice status, WO open/closed status. Nature of work (one-time, monthly, annual RC, POC). BD/KAM owner per work order. Customer-level outstanding amounts. |

---

## Available Tools

No tools take arguments. Each tool fetches the full board and returns all data — the LLM extracts what's relevant to the user's question. This avoids Groq's strict null-argument validation errors with optional parameters.

| Tool | Answers questions about |
|---|---|
| `get_pipeline_summary` | Pipeline value, won value, dead deal value lost, deal counts by status, sector breakdown, open pipeline by BD owner |
| `get_owner_performance` | Deal counts, won value, dead deal value, open pipeline, avg won deal size — for all owners |
| `get_revenue_summary` | Total contracted, billed, collected, unbilled, receivables. Breakdown by nature of work and by BD/KAM owner. Invoice status counts. |
| `get_sector_performance` | Contracted, billed, collected, unbilled, receivable per sector. Execution status, invoice status, and WO open/closed breakdown per sector. |
| `get_collections_status` | Total receivables, customer-level outstanding amounts ranked by size, execution status × receivable/unbilled, stuck work orders |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/nhprasan/bi-agent.git
cd bi-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
MONDAY_API_KEY=your_monday_api_key
```

- Get a Groq API key at [console.groq.com](https://console.groq.com)
- Get a Monday.com API key from your account under **Profile → Admin → API**

### 4. Update board IDs (if needed)

In `config.py`, confirm or update:

```python
DEALS_BOARD_ID       = your_deals_board_id
WORK_ORDERS_BOARD_ID = your_work_orders_board_id
```

### 5. Run the app

```bash
streamlit run app.py
```

---

## Example Questions

```
What is our current pipeline value?
Who is our best performing BD rep?
How much value have we lost in dead deals?
What is our total contracted revenue vs what we've collected?
Which sector generates the most revenue?
How is Mining performing?
How much money is outstanding and which customers owe us the most?
What work orders are stuck or paused?
How are monthly contracts performing financially?
Which BD/KAM manages the most contracted value on work orders?
How is OWNER_003 performing on deals?
Show me the Railways pipeline.
```

---

## Configuration Reference

All domain configuration lives in `config.py`:

| Constant | Purpose |
|---|---|
| `DEAL_FUNNEL_COLUMN_MAP` | Maps Monday column IDs → readable snake_case names |
| `WORK_ORDER_COLUMN_MAP` | Same for the Work Orders board |
| `SECTOR_CANONICAL` | Normalizes sector name variants to a single canonical form |
| `DEAL_NUMERIC_COLS` / `WORK_ORDER_NUMERIC_COLS` | Columns cast to float for aggregation |
| `KNOWN_HEADER_LABELS` | Labels used to drop embedded header rows from Monday exports |
| `DEALS_DQ_COLS` / `WO_DQ_COLS` | Standard column lists passed to the data quality checker in each tool |

## License

MIT