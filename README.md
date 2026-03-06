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
| **Deal Funnel** | All deals — open, won, dead, on hold. Deal value, stage, sector, BD owner, closure probability, dates. |
| **Work Orders** | All contracted work. Contracted value, billed, collected, receivables, execution status, invoice status. |

---

## Available Tools

| Tool | Answers questions about |
|---|---|
| `get_pipeline_summary` | Pipeline value, deal counts by status/stage, open deals by sector and owner |
| `get_owner_performance` | Win rate, loss rate, won value, open pipeline per BD owner |
| `get_weighted_pipeline_value` | Probability-adjusted pipeline (High=75%, Medium=50%, Low=25%) |
| `get_revenue_summary` | Total contracted value, billed, collected, unbilled, receivables |
| `get_sector_performance` | Revenue, billed, collected, receivables broken down by sector |
| `get_collections_status` | Outstanding payments, priority AR accounts, stuck work orders |

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
How many open deals do we have, broken down by stage?
Who is our best performing BD rep?
What is our total contracted revenue vs what we've collected?
Which sector generates the most revenue?
How much money is outstanding and who are the priority accounts?
What is our weighted pipeline value?
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

---

## Notes

- **Data is masked** — client identities and deal values use anonymized codes as configured in Monday.com
- **No time-series** — the agent works with current board state only; historical trend analysis is not supported
- **Token management** — conversation history is trimmed to the last 2 exchanges to stay within LLM context limits
- **Recursion limit** — the graph is capped at 10 node visits per turn to prevent infinite loops

---

## License

MIT