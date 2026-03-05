# All Monday.com API calls live here.
# Each function fetches live data, cleans it via normalizer.py.
# The agent in graph.py wraps these as LangChain tools.

import requests
import time
import random
from config import (
    MONDAY_API_KEY,
    MONDAY_API_URL,
    DEALS_BOARD_ID,
    WORK_ORDERS_BOARD_ID,
    DEALS_COLUMNS,
    WORK_ORDER_COLUMNS,
    DEALS_COL_ID_TO_TITLE,
    WORK_ORDER_COL_ID_TO_TITLE,
)
from agent.normalizer import (
    normalize_date,
    normalize_month,
    normalize_sector,
    normalize_status,
    to_float,
    is_header_row,
    parse_column_values,
)


# ── Shared API helper ────────────────────────────────────────────────────────

def _run_query(query: str, max_retries: int = 3) -> dict:
    """
    Sends a GraphQL query to Monday.com and returns parsed JSON.
    Retries on transient failures (network errors, 5xx, rate limits).
    All tools go through this single function.
    """

    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                MONDAY_API_URL,
                json={"query": query},
                headers=headers,
                timeout=30,
            )

            # Retry on server errors or rate limits
            if response.status_code >= 500 or response.status_code == 429:
                raise RuntimeError(
                    f"Retryable error {response.status_code}: {response.text}"
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Monday API HTTP {response.status_code}: {response.text}"
                )

            data = response.json()

            if "errors" in data:
                raise RuntimeError(f"Monday GraphQL error: {data['errors']}")

            return data

        except (requests.RequestException, RuntimeError) as e:
            if attempt == max_retries:
                raise RuntimeError(f"Monday API failed after {max_retries} attempts: {e}")

            # Exponential backoff with jitter
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)


def _col_ids(column_map: dict) -> str:
    """
    Builds the column IDs string for a GraphQL query.
    Excludes 'name' since that's a top-level item field, not a column value.
    """
    ids = [v for k, v in column_map.items() if k != "name"]
    return ", ".join(f'"{i}"' for i in ids)


# ── Tool 1: Fetch Deals ──────────────────────────────────────────────────────

def fetch_deals(
    sector: str = None,
    status: str = None,
    stage: str = None,
) -> list:
    """
    Fetches all deals from the Deal Funnel board.
    Optional filters: sector, deal status (Open/Won/Dead etc.), deal stage.
    Returns a list of clean deal dicts.
    """
    query = f"""
    query {{
      boards(ids: [{DEALS_BOARD_ID}]) {{
        items_page(limit: 500) {{
          items {{
            id
            name
            column_values(ids: [{_col_ids(DEALS_COLUMNS)}]) {{
              id
              text
            }}
          }}
        }}
      }}
    }}
    """
    raw = _run_query(query)

    try:
        items = raw["data"]["boards"][0]["items_page"]["items"]
    except (KeyError, IndexError):
        return []

    results = []
    for item in items:
        parsed = parse_column_values(item.get("column_values", []), DEALS_COLUMNS)

        deal = {
            "id":   item.get("id"),
            "name": item.get("name", "").strip(),
            **parsed,
        }

        # Drop accidental Excel header rows
        if is_header_row(item, DEALS_COL_ID_TO_TITLE):
            continue

        # Normalize sector to canonical form
        deal["sector"] = normalize_sector(deal.get("sector", ""))

        for field in ["close_date_actual", "tentative_close_date", "created_date"]:
            deal[field] = normalize_date(deal.get(field, ""))

        # Convert deal value to float (Monday returns it as string)
        deal["deal_value"] = to_float(deal.get("deal_value"))

        # Apply optional filters
        if sector and deal["sector"] != normalize_sector(sector):
            continue
        if status and status.lower() not in deal.get("deal_status", "").lower():
            continue
        if stage and stage.lower() not in deal.get("deal_stage", "").lower():
            continue

        results.append(deal)

    return results


# ── Tool 2: Fetch Work Orders ────────────────────────────────────────────────

def fetch_work_orders(
    sector: str = None,
    execution_status: str = None,
    billing_status: str = None,
) -> list:
    """
    Fetches all work orders from the Work Orders board.
    Optional filters: sector, execution status, billing status.
    Returns a list of clean work order dicts.
    """
    query = f"""
    query {{
      boards(ids: [{WORK_ORDERS_BOARD_ID}]) {{
        items_page(limit: 500) {{
          items {{
            id
            name
            column_values(ids: [{_col_ids(WORK_ORDER_COLUMNS)}]) {{
              id
              text
            }}
          }}
        }}
      }}
    }}
    """
    raw = _run_query(query)

    try:
        items = raw["data"]["boards"][0]["items_page"]["items"]
    except (KeyError, IndexError):
        return []

    # Financial fields that need to be converted from string to float
    financial_fields = [
        "amount_excl_gst", "amount_incl_gst",
        "billed_excl_gst", "billed_incl_gst",
        "collected_incl_gst", "to_be_billed_excl_gst",
        "to_be_billed_incl_gst", "amount_receivable",
    ]

    results = []
    for item in items:
        parsed = parse_column_values(item.get("column_values", []), WORK_ORDER_COLUMNS)

        wo = {
            "id":   item.get("id"),
            "name": item.get("name", "").strip(),
            **parsed,
        }

        # Drop accidental Excel header rows
        if is_header_row(item, WORK_ORDER_COL_ID_TO_TITLE):
            continue

        # Normalize fields
        wo["sector"] = normalize_sector(wo.get("sector", ""))
        wo["billing_status"] = normalize_status(wo.get("billing_status", ""))
        wo["last_recurring_month"] = normalize_month(wo.get("last_recurring_month", ""))
        wo["actual_billing_month"] = normalize_month(wo.get("actual_billing_month", ""))

        for field in ["data_delivery_date", "po_loi_date", "probable_start_date", 
                      "probable_end_date", "last_invoice_date"]:
            wo[field] = normalize_date(wo.get(field, ""))

        for field in financial_fields:
            wo[field] = to_float(wo.get(field))

        # Apply optional filters
        if sector and wo["sector"] != normalize_sector(sector):
            continue
        if execution_status and execution_status.lower() not in wo.get("execution_status", "").lower():
            continue
        if billing_status and billing_status.lower() not in wo.get("billing_status", "").lower():
            continue

        results.append(wo)

    return results


# ── Tool 3: Pipeline Summary ─────────────────────────────────────────────────

def get_pipeline_summary(sector: str = None) -> dict:
    """
    Aggregates deals into a pipeline overview grouped by sector.
    """
    deals = fetch_deals(sector=sector)

    by_sector = {}
    total_value = 0.0
    missing_value_count = 0

    for deal in deals:
        s = deal.get("sector") or "Unknown"
        value = deal.get("deal_value")
        stage = deal.get("deal_stage") or "Unknown"
        status = deal.get("deal_status") or "Unknown"

        if value is None:
            missing_value_count += 1
            value = 0.0
        total_value += value

        if s not in by_sector:
            by_sector[s] = {"deal_count": 0, "total_value": 0.0, "by_stage": {}, "by_status": {}}

        by_sector[s]["deal_count"] += 1
        by_sector[s]["total_value"] += value
        by_sector[s]["by_stage"][stage] = by_sector[s]["by_stage"].get(stage, 0) + 1
        by_sector[s]["by_status"][status] = by_sector[s]["by_status"].get(status, 0) + 1

    return {
        "total_deals": len(deals),
        "total_pipeline_value": total_value,
        "deals_with_value": len(deals) - missing_value_count,
        "deals_missing_value": missing_value_count,
        "by_sector": by_sector,
    }


# ── Tool 4: Revenue Summary ──────────────────────────────────────────────────

def get_revenue_summary(sector: str = None) -> dict:
    """
    Aggregates work order financials grouped by sector.
    """
    work_orders = fetch_work_orders(sector=sector)

    by_sector = {}
    totals = {
        # Revenue (Ex GST)
        "contract_value": 0.0,
        "billed": 0.0,
        "to_be_billed": 0.0,
        
        # Cash (Incl GST)
        "collected": 0.0,
        "receivable": 0.0,
        }

    for wo in work_orders:
        s = wo.get("sector") or "Unknown"

        contract   = wo.get("amount_excl_gst") or 0.0
        billed     = wo.get("billed_excl_gst") or 0.0
        collected  = wo.get("collected_incl_gst") or 0.0
        receivable = wo.get("amount_receivable") or 0.0
        to_bill    = wo.get("to_be_billed_excl_gst") or 0.0

        totals["contract_value"] += contract
        totals["billed"]         += billed
        totals["collected"]      += collected
        totals["receivable"]     += receivable
        totals["to_be_billed"]   += to_bill

        if s not in by_sector:
            by_sector[s] = {"work_order_count": 0, "contract_value": 0.0,
                            "billed": 0.0, "collected": 0.0,
                            "receivable": 0.0, "to_be_billed": 0.0}

        by_sector[s]["work_order_count"] += 1
        by_sector[s]["contract_value"]   += contract
        by_sector[s]["billed"]           += billed
        by_sector[s]["collected"]        += collected
        by_sector[s]["receivable"]       += receivable
        by_sector[s]["to_be_billed"]     += to_bill

    # Billing efficiency = how much of contract value has been invoiced
    billing_eff = (
        totals["billed"] / totals["contract_value"]
        if totals["contract_value"] > 0 else 0.0
    )

    collection_eff = (
        totals["collected"] / totals["billed"]
        if totals["billed"] > 0 else 0.0
        )

    return {
        "total_work_orders": len(work_orders),
        **totals,
        "billing_efficiency": round(billing_eff, 4),
        "collection_efficiency": round(collection_eff, 4),
        "by_sector": by_sector,
        }


# ── Tool 5: Cross-Board Summary ──────────────────────────────────────────────

def get_cross_board_summary() -> dict:
    """
    Compares pipeline (Deals) vs execution (Work Orders) side by side.
    """
    deals = fetch_deals()
    work_orders = fetch_work_orders()

    pipeline = {}   # sector -> {pipeline_value, deal_count}
    execution = {}  # sector -> {contract_value, work_order_count}

    deal_names = set()
    wo_names = set()

    for deal in deals:
        s = deal.get("sector") or "Unknown"
        deal_names.add((deal.get("name") or "").strip().lower())
        if s not in pipeline:
            pipeline[s] = {"pipeline_value": 0.0, "deal_count": 0}
        pipeline[s]["pipeline_value"] += deal.get("deal_value") or 0.0
        pipeline[s]["deal_count"] += 1

    for wo in work_orders:
        s = wo.get("sector") or "Unknown"
        wo_names.add((wo.get("name") or "").strip().lower())
        if s not in execution:
            execution[s] = {"contract_value": 0.0, "work_order_count": 0}
        execution[s]["contract_value"] += wo.get("amount_excl_gst") or 0.0
        execution[s]["work_order_count"] += 1

    # Work orders whose deal name doesn't exist in the Deals board
    orphaned = wo_names - deal_names

    # Build merged sector view
    all_sectors = set(pipeline.keys()) | set(execution.keys())
    by_sector = {}
    for s in all_sectors:
        p = pipeline.get(s, {})
        e = execution.get(s, {})
        by_sector[s] = {
            "deal_count":        p.get("deal_count", 0),
            "pipeline_value":    p.get("pipeline_value", 0.0),
            "work_order_count":  e.get("work_order_count", 0),
            "contract_value":    e.get("contract_value", 0.0),
        }

    return {
        "by_sector": by_sector,
        "orphaned_work_orders": len(orphaned),
        "data_notes": [
            f"{len(orphaned)} work orders have no matching deal in the Deals board.",
            f"{len(deal_names - wo_names)} deals have not yet generated a work order.",
        ],
    }