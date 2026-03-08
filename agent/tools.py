"""
agent/tools.py

Five BI tools that pull live data from Monday.com and return aggregated results.
No filter arguments on any tool — the LLM reads the full result and picks out
what the user asked about. This sidesteps Groq's strict null-argument validation
errors that were breaking tool calls with optional parameters.

Tools are decorated with @tool directly here.
graph.py just imports them — no wrapper code needed there.

Deals Board      : get_pipeline_summary, get_owner_performance
Work Orders Board: get_revenue_summary, get_sector_performance, get_collections_status
"""

import json
import requests
import pandas as pd
from langchain_core.tools import tool

from config import (
    MONDAY_API_KEY,
    MONDAY_API_URL,
    DEALS_BOARD_ID,
    WORK_ORDERS_BOARD_ID,
    DEALS_DQ_COLS,
    WO_DQ_COLS,
)
from agent.normalizer import normalize_deal_funnel, normalize_work_orders


# ---------------------------------------------------------------------------
# Monday.com fetch — paginated GraphQL
# ---------------------------------------------------------------------------

# Monday caps each page at 500 rows, so we loop until there's no next cursor.
_BOARD_QUERY = """
query GetBoardItems($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        column_values { id text type }
      }
    }
  }
}
"""


def _fetch_all_items(board_id: int) -> dict:
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type":  "application/json",
        "API-Version":   "2024-01",
    }
    all_items = []
    cursor    = None

    while True:
        payload = {
            "query":     _BOARD_QUERY,
            "variables": {"board_id": str(board_id), "limit": 500, "cursor": cursor},
        }
        resp = requests.post(MONDAY_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        page = resp.json()["data"]["boards"][0]["items_page"]
        all_items.extend(page["items"])
        cursor = page.get("cursor")
        if not cursor:
            break

    # rewrap into the shape the normalizer expects
    return {"data": {"boards": [{"items_page": {"items": all_items}}]}}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _has_value(v) -> bool:
    # blank strings come through from Monday for empty cells — treat them as missing
    return isinstance(v, str) and v.strip() != ""


def _count_missing(df: pd.DataFrame, cols: list) -> dict:
    # returns {col: count} for any column that has gaps, plus a total_rows key
    # the LLM uses this to flag data quality issues in its response
    result = {"total_rows": len(df)}
    for col in cols:
        if col not in df.columns:
            continue
        n = df[col].apply(
            lambda v: v is None
            or (isinstance(v, float) and pd.isna(v))
            or (isinstance(v, str) and v.strip() == "")
        ).sum()
        if n > 0:
            result[col] = int(n)
    return result


def _fin_groupby(df: pd.DataFrame, group_col: str, label_key: str) -> list:
    # standard financial rollup used by revenue_summary for both
    # nature_of_work and bd_kam breakdowns — avoids repeating the same pattern
    rows = []
    for val, grp in df[df[group_col].apply(_has_value)].groupby(group_col):
        rows.append({
            label_key:    val,
            "wo_count":   len(grp),
            "contracted": round(grp["amount_excl_gst_masked"].sum(skipna=True), 2),
            "billed":     round(grp["billed_value_excl_gst_masked"].sum(skipna=True), 2),
            "collected":  round(grp["collected_amount_incl_gst_masked"].sum(skipna=True), 2),
            "receivable": round(grp["amount_receivable_masked"].sum(skipna=True), 2),
        })
    rows.sort(key=lambda x: x["contracted"], reverse=True)
    return rows


def _status_counts(df: pd.DataFrame, col: str) -> dict:
    # simple value_counts for a categorical column, blank rows excluded
    return df[df[col].apply(_has_value)][col].value_counts().to_dict()


# ---------------------------------------------------------------------------
# Tool 1 — Pipeline Summary
# Deals Board. Returns everything: all statuses, all sectors, all owners.
# ---------------------------------------------------------------------------

@tool
def get_pipeline_summary() -> str:
    """
    Use for any question about the sales pipeline.
    Returns all deals across all statuses (open, won, dead, on hold).
    Includes totals, sector breakdown, and open pipeline by owner.

    Good for: pipeline value, won value, dead deal value, deal counts by status,
    sector-level pipeline, which BD owns the most open deals.
    """
    raw = _fetch_all_items(DEALS_BOARD_ID)
    df  = normalize_deal_funnel(raw)

    open_df = df[df["deal_status"] == "open"]
    won_df  = df[df["deal_status"] == "won"]
    dead_df = df[df["deal_status"] == "dead"]

    # one row per sector with counts and values split by status
    sector_rows = []
    for sec, grp in df[df["sector"].apply(_has_value)].groupby("sector"):
        sector_rows.append({
            "sector":      sec,
            "total_deals": len(grp),
            "open_deals":  len(grp[grp["deal_status"] == "open"]),
            "won_deals":   len(grp[grp["deal_status"] == "won"]),
            "dead_deals":  len(grp[grp["deal_status"] == "dead"]),
            "open_value":  round(grp[grp["deal_status"] == "open"]["deal_value_masked"].sum(skipna=True), 2),
            "won_value":   round(grp[grp["deal_status"] == "won"]["deal_value_masked"].sum(skipna=True), 2),
            "dead_value":  round(grp[grp["deal_status"] == "dead"]["deal_value_masked"].sum(skipna=True), 2),
        })
    sector_rows.sort(key=lambda x: x["won_value"], reverse=True)

    # open pipeline only per owner — closed deals don't reflect current accountability
    owner_rows = []
    for owner, grp in open_df[open_df["owner_code"].apply(_has_value)].groupby("owner_code"):
        owner_rows.append({
            "owner_code":     owner,
            "open_deals":     len(grp),
            "pipeline_value": round(grp["deal_value_masked"].sum(skipna=True), 2),
        })
    owner_rows.sort(key=lambda x: x["pipeline_value"], reverse=True)

    return json.dumps({
        "status_counts":        df["deal_status"].value_counts().to_dict(),
        "open_deals_count":     len(open_df),
        "total_pipeline_value": round(open_df["deal_value_masked"].sum(skipna=True), 2),
        "total_won_value":      round(won_df["deal_value_masked"].sum(skipna=True), 2),
        "total_dead_value":     round(dead_df["deal_value_masked"].sum(skipna=True), 2),
        "sector_breakdown":     sector_rows,
        "owner_breakdown":      owner_rows,
        "data_quality":         _count_missing(df, DEALS_DQ_COLS),
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 2 — Owner Performance
# Deals Board. Returns stats for every owner — LLM picks the right one.
# ---------------------------------------------------------------------------

@tool
def get_owner_performance() -> str:
    """
    Use for any question about individual BD/sales owner performance on deals.
    Returns stats for all owners — won value, dead value, open pipeline, deal counts.

    Good for: who is the best performer, how is OWNER_X doing, who has lost
    the most in dead deals, average won deal size per BD.
    """
    raw = _fetch_all_items(DEALS_BOARD_ID)
    df  = normalize_deal_funnel(raw)

    # rows with no owner assigned can't be attributed to anyone
    df_owners = df[df["owner_code"].apply(_has_value)]

    owners = []
    for owner, grp in df_owners.groupby("owner_code"):
        won   = grp[grp["deal_status"] == "won"]
        dead  = grp[grp["deal_status"] == "dead"]
        open_ = grp[grp["deal_status"] == "open"]
        avg   = won["deal_value_masked"].mean(skipna=True)
        owners.append({
            "owner_code":          owner,
            "total_deals":         len(grp),
            "won_deals":           len(won),
            "dead_deals":          len(dead),
            "open_deals":          len(open_),
            "total_won_value":     round(won["deal_value_masked"].sum(skipna=True), 2),
            "total_dead_value":    round(dead["deal_value_masked"].sum(skipna=True), 2),
            "open_pipeline_value": round(open_["deal_value_masked"].sum(skipna=True), 2),
            # guard against NaN when all won deal values are blank
            "avg_won_deal_size":   round(avg, 2) if len(won) and not pd.isna(avg) else None,
        })
    owners.sort(key=lambda x: x["total_won_value"], reverse=True)

    dq = _count_missing(df, DEALS_DQ_COLS)
    dq["rows_excluded_no_owner"] = int(len(df) - len(df_owners))

    return json.dumps({
        "owner_performance": owners,
        "data_quality":      dq,
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 3 — Revenue Summary
# Work Orders Board. Company-wide financial totals + breakdowns.
# ---------------------------------------------------------------------------

@tool
def get_revenue_summary() -> str:
    """
    Use for any question about overall company revenue and work order financials.
    Returns totals plus breakdowns by nature of work and by BD/KAM owner.

    Good for: total contracted vs billed vs collected, unbilled amount,
    receivables, how monthly/one-time/POC contracts are performing,
    which BD/KAM manages the most contracted value.
    """
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    def _sum(col):
        return round(df[col].sum(skipna=True), 2) if col in df.columns else 0

    return json.dumps({
        "total_contracted_excl_gst": _sum("amount_excl_gst_masked"),
        "total_contracted_incl_gst": _sum("amount_incl_gst_masked"),
        "total_billed_excl_gst":     _sum("billed_value_excl_gst_masked"),
        "total_billed_incl_gst":     _sum("billed_value_incl_gst_masked"),
        "total_collected":           _sum("collected_amount_incl_gst_masked"),
        "total_unbilled_excl_gst":   _sum("amount_to_be_billed_excl_gst_masked"),
        "total_receivable":          _sum("amount_receivable_masked"),
        "invoice_status_breakdown":  _status_counts(df, "invoice_status"),
        "nature_of_work_breakdown":  _fin_groupby(df, "nature_of_work", "nature_of_work"),
        "bd_kam_breakdown":          _fin_groupby(df, "bd_kam_personnel_code", "bd_kam_code"),
        "data_quality":              _count_missing(df, WO_DQ_COLS),
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 4 — Sector Performance
# Work Orders Board. Returns all sectors — LLM picks the right one.
# ---------------------------------------------------------------------------

@tool
def get_sector_performance() -> str:
    """
    Use for any question about work order performance broken down by sector.
    Returns all sectors — the LLM picks out the relevant one from the results.

    Good for: which sector generates the most revenue, how is Mining/Railways/
    Renewables performing, sector-level billed vs collected, unbilled by sector,
    execution and invoice status breakdown per sector.
    """
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    # rows with no sector filled in can't be grouped
    df_sector = df[df["sector"].apply(_has_value)]

    sectors = []
    for sec, grp in df_sector.groupby("sector"):
        sectors.append({
            "sector":                     sec,
            "work_order_count":           len(grp),
            "contracted_excl_gst":        round(grp["amount_excl_gst_masked"].sum(skipna=True), 2),
            "billed_excl_gst":            round(grp["billed_value_excl_gst_masked"].sum(skipna=True), 2),
            "collected":                  round(grp["collected_amount_incl_gst_masked"].sum(skipna=True), 2),
            "unbilled_excl_gst":          round(grp["amount_to_be_billed_excl_gst_masked"].sum(skipna=True), 2),
            "receivable":                 round(grp["amount_receivable_masked"].sum(skipna=True), 2),
            "execution_status_breakdown": _status_counts(grp, "execution_status"),
            "invoice_status_breakdown":   _status_counts(grp, "invoice_status"),
            "wo_status_breakdown":        _status_counts(grp, "wo_status_billed"),
        })
    sectors.sort(key=lambda x: x["contracted_excl_gst"], reverse=True)

    dq = _count_missing(df, WO_DQ_COLS)
    dq["rows_excluded_no_sector"] = int(len(df) - len(df_sector))

    return json.dumps({
        "sector_performance": sectors,
        "data_quality":       dq,
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 5 — Collections Status
# Work Orders Board. Outstanding amounts, stuck WOs, customer-level view.
# ---------------------------------------------------------------------------

@tool
def get_collections_status() -> str:
    """
    Use for any question about outstanding payments, receivables, or stuck work.
    Returns customer-level outstanding amounts, execution status financials,
    and a list of work orders that are paused or blocked.

    Good for: how much is outstanding, which customers owe us the most,
    what work is stuck, which execution status has the most unbilled value.
    """
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    # only rows with actual money outstanding
    receivable_df = df[
        df["amount_receivable_masked"].notna() &
        (df["amount_receivable_masked"] > 0)
    ].sort_values("amount_receivable_masked", ascending=False)

    customer_outstanding = receivable_df[[
        "deal_name", "customer_name_code", "sector",
        "nature_of_work", "execution_status",
        "amount_receivable_masked", "billed_value_incl_gst_masked",
        "collected_amount_incl_gst_masked", "wo_status_billed",
    ]].to_dict(orient="records")

    # how much money is blocked at each execution status
    exec_rows = []
    for status, grp in df[df["execution_status"].apply(_has_value)].groupby("execution_status"):
        exec_rows.append({
            "execution_status": status,
            "wo_count":         len(grp),
            "receivable":       round(grp["amount_receivable_masked"].sum(skipna=True), 2),
            "unbilled":         round(grp["amount_to_be_billed_excl_gst_masked"].sum(skipna=True), 2),
        })
    exec_rows.sort(key=lambda x: x["receivable"], reverse=True)

    # WOs that are explicitly paused or waiting on client — these are the ones to chase
    stuck = df[
        df["execution_status"].apply(
            lambda v: isinstance(v, str)
            and v.strip() in {"pause / struck", "details pending from client"}
        )
    ][[
        "deal_name", "customer_name_code", "sector",
        "execution_status", "amount_receivable_masked",
        "amount_to_be_billed_excl_gst_masked",
    ]].to_dict(orient="records")

    return json.dumps({
        "total_receivable":            round(receivable_df["amount_receivable_masked"].sum(), 2),
        "customer_outstanding":        customer_outstanding,
        "execution_status_financials": exec_rows,
        "stuck_work_orders":           stuck,
        "wo_status_breakdown":         _status_counts(df, "wo_status_billed"),
        "data_quality":                _count_missing(df, WO_DQ_COLS),
    }, default=str)