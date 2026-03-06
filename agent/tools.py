"""
agent/tools.py

Six BI tools for founder/executive queries.
Each tool fetches live data, normalizes it, computes analysis,
and always returns a data_quality dict for the LLM to use as caveats.

Deals Board:
  - get_pipeline_summary
  - get_owner_performance
  - get_weighted_pipeline_value

Work Orders Board:
  - get_revenue_summary
  - get_sector_performance
  - get_collections_status
"""
# NOTE: no caching here — every call hits the Monday API fresh.
# Keeps data live but means two tools in one turn fetch the board separately.

import requests
import pandas as pd

from config import (
    MONDAY_API_KEY,
    MONDAY_API_URL,
    DEALS_BOARD_ID,
    WORK_ORDERS_BOARD_ID,
)
from agent.normalizer import normalize_deal_funnel, normalize_work_orders


# ---------------------------------------------------------------------------
# GraphQL fetch with pagination
# ---------------------------------------------------------------------------

# Monday.com caps items_page at 500 per request, so we loop using cursors.
_BOARD_QUERY = """
query GetBoardItems($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        column_values {
          id
          text
          type
        }
      }
    }
  }
}
"""


def _fetch_all_items(board_id: int) -> dict:
    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }
    all_items = []
    cursor = None  # first request has no cursor; Monday returns one if more pages exist

    while True:
        payload = {
            "query": _BOARD_QUERY,
            "variables": {
                "board_id": str(board_id),
                "limit": 500,
                "cursor": cursor,
            },
        }
        response = requests.post(MONDAY_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        board_data = data["data"]["boards"][0]["items_page"]
        all_items.extend(board_data["items"])

        cursor = board_data.get("cursor")
        if not cursor:  # no cursor = last page
            break

    # rewrap into the same shape the normalizer expects
    return {"data": {"boards": [{"items_page": {"items": all_items}}]}}


# ---------------------------------------------------------------------------
# Data quality helper
# ---------------------------------------------------------------------------

def _count_missing(df: pd.DataFrame, cols: list) -> dict:
    """
    Returns {col: missing_count} for columns with any missing values,
    plus total_rows. The LLM uses this to compute percentages and add caveats.
    """
    result = {"total_rows": len(df)}
    for col in cols:
        if col not in df.columns:
            continue
        # treat None, NaN, and blank strings uniformly as missing
        missing = df[col].apply(
            lambda v: v is None
            or (isinstance(v, float) and pd.isna(v))
            or (isinstance(v, str) and v.strip() == "")
        ).sum()
        if missing > 0:
            result[col] = int(missing)
    return result


# ---------------------------------------------------------------------------
# Tool 1: Pipeline Summary (Deals)
# ---------------------------------------------------------------------------

def get_pipeline_summary() -> dict:
    raw = _fetch_all_items(DEALS_BOARD_ID)
    df  = normalize_deal_funnel(raw)

    # split early — most metrics below are scoped to either open or won deals
    open_df = df[df["deal_status"] == "open"].copy()
    won_df  = df[df["deal_status"] == "won"].copy()

    # sector and owner breakdowns are open-only; skip rows with blank values
    sector_breakdown = (
        open_df[open_df["sector"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
        .groupby("sector")
        .agg(deal_count=("deal_name", "count"), pipeline_value=("deal_value_masked", "sum"))
        .reset_index()
        .sort_values("pipeline_value", ascending=False)
        .to_dict(orient="records")
    )

    owner_breakdown = (
        open_df[open_df["owner_code"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
        .groupby("owner_code")
        .agg(deal_count=("deal_name", "count"), pipeline_value=("deal_value_masked", "sum"))
        .reset_index()
        .sort_values("pipeline_value", ascending=False)
        .to_dict(orient="records")
    )

    return {
        "status_counts":        df["deal_status"].value_counts().to_dict(),  # open/won/dead/on hold
        "open_deals_count":     len(open_df),
        "total_pipeline_value": round(open_df["deal_value_masked"].sum(skipna=True), 2),
        "total_won_value":      round(won_df["deal_value_masked"].sum(skipna=True), 2),
        "stage_breakdown":      open_df["deal_stage"].value_counts().to_dict(),
        "sector_breakdown":     sector_breakdown,
        "owner_breakdown":      owner_breakdown,
        "data_quality":         _count_missing(df, [
            "deal_value_masked", "deal_status", "deal_stage",
            "sector", "owner_code", "closure_probability", "tentative_close_date",
        ]),
    }


# ---------------------------------------------------------------------------
# Tool 2: Owner Performance (Deals)
# ---------------------------------------------------------------------------

def get_owner_performance() -> dict:
    raw = _fetch_all_items(DEALS_BOARD_ID)
    df  = normalize_deal_funnel(raw)

    # exclude rows with no owner before grouping
    has_owner = df["owner_code"].apply(lambda v: isinstance(v, str) and v.strip() != "")
    df_owners = df[has_owner]

    owners = []
    for owner, grp in df_owners.groupby("owner_code"):
        total      = len(grp)
        won        = len(grp[grp["deal_status"] == "won"])
        dead       = len(grp[grp["deal_status"] == "dead"])
        open_count = len(grp[grp["deal_status"] == "open"])
        owners.append({
            "owner_code":          owner,
            "total_deals":         total,
            "won_deals":           won,
            "win_rate_pct":        round((won / total) * 100, 1) if total else 0,
            "dead_deals":          dead,
            "loss_rate_pct":       round((dead / total) * 100, 1) if total else 0,
            "open_deals":          open_count,
            "total_won_value":     round(grp[grp["deal_status"] == "won"]["deal_value_masked"].sum(skipna=True), 2),
            "open_pipeline_value": round(grp[grp["deal_status"] == "open"]["deal_value_masked"].sum(skipna=True), 2),
        })

    # sort by won value so the best performer appears first
    owners.sort(key=lambda x: x["total_won_value"], reverse=True)

    dq = _count_missing(df, ["owner_code", "deal_value_masked", "deal_status"])
    dq["rows_excluded_no_owner"] = int(len(df) - len(df_owners))  # lets the LLM flag unassigned deals

    return {
        "owner_performance": owners,
        "data_quality":      dq,
    }


# ---------------------------------------------------------------------------
# Tool 3: Weighted Pipeline Value (Deals)
# ---------------------------------------------------------------------------

def get_weighted_pipeline_value() -> dict:
    """
    Maps closure probability to numeric weights and computes a
    probability-adjusted pipeline value for open deals.
      High -> 75%, Medium -> 50%, Low -> 25%
    """
    PROB_WEIGHTS = {"high": 0.75, "medium": 0.50, "low": 0.25}

    raw = _fetch_all_items(DEALS_BOARD_ID)
    df  = normalize_deal_funnel(raw)

    open_df        = df[df["deal_status"] == "open"].copy()
    total_raw      = 0.0
    total_weighted = 0.0
    breakdown      = []

    for prob_label, weight in PROB_WEIGHTS.items():
        tier_df    = open_df[open_df["closure_probability"] == prob_label]
        with_value = tier_df[tier_df["deal_value_masked"].notna()]  # skip deals with no value filled in
        raw_val    = with_value["deal_value_masked"].sum(skipna=True)
        weighted   = raw_val * weight
        total_raw      += raw_val
        total_weighted += weighted

        breakdown.append({
            "closure_probability": prob_label,
            "weight_pct":          int(weight * 100),
            "deal_count":          len(tier_df),
            "deals_with_value":    len(with_value),
            "raw_pipeline_value":  round(raw_val, 2),
            "weighted_value":      round(weighted, 2),
        })

    # deals with no probability set are excluded from the weighted calc
    no_prob = open_df[
        ~open_df["closure_probability"].isin(list(PROB_WEIGHTS.keys()))
    ]

    return {
        "open_deals_total":          len(open_df),
        "deals_in_weighted_calc":    int(open_df["closure_probability"].isin(list(PROB_WEIGHTS.keys())).sum()),
        "deals_excluded_no_prob":    len(no_prob),
        "raw_pipeline_value":        round(total_raw, 2),
        "weighted_pipeline_value":   round(total_weighted, 2),
        "breakdown_by_probability":  breakdown,
        "data_quality":              _count_missing(open_df, [
            "closure_probability", "deal_value_masked",
        ]),
    }


# ---------------------------------------------------------------------------
# Tool 4: Revenue Summary (Work Orders)
# ---------------------------------------------------------------------------

def get_revenue_summary() -> dict:
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    # helper to safely sum a column — returns 0 if the column doesn't exist
    def _sum(col):
        return round(df[col].sum(skipna=True), 2) if col in df.columns else 0

    return {
        "total_contracted_excl_gst": _sum("amount_excl_gst_masked"),
        "total_contracted_incl_gst": _sum("amount_incl_gst_masked"),
        "total_billed_excl_gst":     _sum("billed_value_excl_gst_masked"),
        "total_billed_incl_gst":     _sum("billed_value_incl_gst_masked"),
        "total_collected":           _sum("collected_amount_incl_gst_masked"),
        "total_unbilled_excl_gst":   _sum("amount_to_be_billed_excl_gst_masked"),
        "total_receivable":          _sum("amount_receivable_masked"),
        # status breakdowns — blank values filtered before counting
        "billing_status_breakdown":  (
            df[df["billing_status"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
            ["billing_status"].value_counts().to_dict()
        ),
        "invoice_status_breakdown":  (
            df[df["invoice_status"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
            ["invoice_status"].value_counts().to_dict()
        ),
        "nature_of_work_breakdown":  (
            df[df["nature_of_work"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
            ["nature_of_work"].value_counts().to_dict()
        ),
        "data_quality": _count_missing(df, [
            "amount_excl_gst_masked", "amount_incl_gst_masked",
            "billed_value_excl_gst_masked", "collected_amount_incl_gst_masked",
            "amount_receivable_masked", "billing_status", "invoice_status", "nature_of_work",
        ]),
    }


# ---------------------------------------------------------------------------
# Tool 5: Sector Performance (Work Orders)
# ---------------------------------------------------------------------------

def get_sector_performance() -> dict:
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    # exclude rows with no sector — can't meaningfully group them
    has_sector = df["sector"].apply(lambda v: isinstance(v, str) and v.strip() != "")
    df_sector  = df[has_sector]

    sectors = []
    for sector, grp in df_sector.groupby("sector"):
        exec_status = (
            grp[grp["execution_status"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
            ["execution_status"].value_counts().to_dict()
        )
        sectors.append({
            "sector":                     sector,
            "work_order_count":           len(grp),
            "contracted_excl_gst":        round(grp["amount_excl_gst_masked"].sum(skipna=True), 2),
            "billed_excl_gst":            round(grp["billed_value_excl_gst_masked"].sum(skipna=True), 2),
            "collected":                  round(grp["collected_amount_incl_gst_masked"].sum(skipna=True), 2),
            "receivable":                 round(grp["amount_receivable_masked"].sum(skipna=True), 2),
            "execution_status_breakdown": exec_status,
        })

    # sort by contracted value so the biggest sector appears first
    sectors.sort(key=lambda x: x["contracted_excl_gst"], reverse=True)

    dq = _count_missing(df, [
        "sector", "amount_excl_gst_masked",
        "billed_value_excl_gst_masked", "collected_amount_incl_gst_masked", "execution_status",
    ])
    dq["rows_excluded_no_sector"] = int(len(df) - len(df_sector))

    return {
        "sector_performance": sectors,
        "data_quality":       dq,
    }


# ---------------------------------------------------------------------------
# Tool 6: Collections Status (Work Orders)
# ---------------------------------------------------------------------------

def get_collections_status() -> dict:
    raw = _fetch_all_items(WORK_ORDERS_BOARD_ID)
    df  = normalize_work_orders(raw)

    # only include work orders that actually have money outstanding
    receivable_df = df[
        df["amount_receivable_masked"].notna() &
        (df["amount_receivable_masked"] > 0)
    ].sort_values("amount_receivable_masked", ascending=False)

    # full list of accounts with outstanding amounts, largest first
    outstanding = receivable_df[[
        "deal_name", "customer_name_code", "serial_number", "sector",
        "amount_receivable_masked", "billed_value_incl_gst_masked",
        "collected_amount_incl_gst_masked", "ar_priority_account",
        "billing_status", "wo_status_billed",
    ]].to_dict(orient="records")

    # subset flagged as priority by the ops/finance team
    priority_accounts = (
        df[df["ar_priority_account"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
        [["deal_name", "customer_name_code", "serial_number",
          "amount_receivable_masked", "ar_priority_account"]]
        .to_dict(orient="records")
    )

    # work orders stuck in pause or waiting on client — likely blocking billing
    stuck = df[
        df["execution_status"].apply(
            lambda v: isinstance(v, str)
            and v.strip() in {"pause / struck", "details pending from client"}
        )
    ][[
        "deal_name", "customer_name_code", "serial_number",
        "sector", "execution_status", "amount_receivable_masked",
    ]].to_dict(orient="records")

    return {
        "total_receivable":     round(receivable_df["amount_receivable_masked"].sum(), 2),
        "outstanding_accounts": outstanding,
        "priority_ar_accounts": priority_accounts,
        "wo_status_breakdown":  (
            df[df["wo_status_billed"].apply(lambda v: isinstance(v, str) and v.strip() != "")]
            ["wo_status_billed"].value_counts().to_dict()
        ),
        "stuck_work_orders":    stuck,
        "data_quality":         _count_missing(df, [
            "amount_receivable_masked", "collected_amount_incl_gst_masked",
            "billed_value_incl_gst_masked", "wo_status_billed",
            "billing_status", "ar_priority_account", "collection_status", "collection_date",
        ]),
    }