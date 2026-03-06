"""
agent/normalizer.py

Cleans and normalizes raw Monday.com GraphQL responses for both boards.
All constants and domain config live in config.py.
"""

import pandas as pd

from config import (
    DEAL_FUNNEL_COLUMN_MAP,
    WORK_ORDER_COLUMN_MAP,
    SECTOR_CANONICAL,
    DEAL_LOWERCASE_COLS,
    WORK_ORDER_LOWERCASE_COLS,
    DEAL_NUMERIC_COLS,
    WORK_ORDER_NUMERIC_COLS,
    KNOWN_HEADER_LABELS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_items(board_response: dict) -> list:
    """Pull the items list out of a Monday.com GraphQL response."""
    if "data" in board_response:
        for v in board_response["data"].values():
            if isinstance(v, list) and v:
                board_response = v
                break
    if isinstance(board_response, list):
        board_response = board_response[0]
    return board_response.get("items_page", {}).get("items", [])


def _items_to_df(items: list, column_map: dict) -> pd.DataFrame:
    """Convert Monday.com items list into a raw DataFrame."""
    records = []
    for item in items:
        # start each row with the item name and its Monday ID
        row = {
            "deal_name":      item.get("name", ""),
            "monday_item_id": item.get("id", ""),
        }
        # index column values by their column ID for fast lookup
        col_index = {cv["id"]: cv.get("text", "") for cv in item.get("column_values", [])}
        # map each column ID to its readable name and pull the value
        for col_id, col_name in column_map.items():
            row[col_name] = col_index.get(col_id, "")
        records.append(row)
    return pd.DataFrame(records)


def _drop_embedded_headers(df: pd.DataFrame, column_map: dict) -> pd.DataFrame:
    """Drop rows where cell values are literal column header text.
    Monday sometimes includes group title rows as actual data items."""
    all_known = (
        KNOWN_HEADER_LABELS
        | {k.lower() for k in column_map.keys()}
        | {v.lower() for v in column_map.values()}
    )

    def is_header_row(row):
        str_vals = [str(v).strip().lower() for v in row if isinstance(v, str) and v.strip()]
        if not str_vals:
            return False
        # if 30%+ of the populated cells match known header labels, treat as a header row
        return sum(1 for v in str_vals if v in all_known) / len(str_vals) >= 0.30

    mask = df.apply(is_header_row, axis=1)
    return df[~mask].reset_index(drop=True)


def _standardize_sector(df: pd.DataFrame) -> pd.DataFrame:
    """Map sector values to canonical names. Blank values are left as-is."""
    if "sector" not in df.columns:
        return df
    def _map(v):
        if not isinstance(v, str) or not v.strip():
            return v
        # unrecognized values pass through as-is rather than being silently dropped
        return SECTOR_CANONICAL.get(v.strip().lower(), v)
    df["sector"] = df["sector"].apply(_map)
    return df


def _apply_lowercase(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Lowercase categorical columns. Blank values are left as-is."""
    for col in cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(
            lambda v: v.strip().lower() if isinstance(v, str) and v.strip() else v
        )
    return df


def _cast_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Cast numeric columns to float for aggregation.
    Strips commas before casting (handles Indian formatting e.g. "1,23,456.78").
    Blank strings, None, and non-numeric strings like '#VALUE!' become None."""
    for col in cols:
        if col not in df.columns:
            continue
        def _to_float(v):
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                v = v.strip().replace(",", "")
                if not v:
                    return None
                try:
                    return float(v)
                except ValueError:
                    return None  # e.g. formula errors from Monday
        df[col] = df[col].apply(_to_float)
    return df


def _drop_full_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows identical across all business columns.
    monday_item_id is excluded because it's always unique — we want to catch
    rows where all the actual content is the same regardless of ID."""
    check_cols = [c for c in df.columns if c != "monday_item_id"]
    return df.drop_duplicates(subset=check_cols).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_deal_funnel(board_response: dict) -> pd.DataFrame:
    items = _extract_items(board_response)
    if not items:
        return pd.DataFrame()

    df = _items_to_df(items, DEAL_FUNNEL_COLUMN_MAP)
    df = _drop_embedded_headers(df, DEAL_FUNNEL_COLUMN_MAP)
    df = _standardize_sector(df)
    df = _apply_lowercase(df, DEAL_LOWERCASE_COLS)
    df = _cast_numeric(df, DEAL_NUMERIC_COLS)
    df = _drop_full_duplicates(df)
    return df


def normalize_work_orders(board_response: dict) -> pd.DataFrame:
    items = _extract_items(board_response)
    if not items:
        return pd.DataFrame()

    df = _items_to_df(items, WORK_ORDER_COLUMN_MAP)
    df = _drop_embedded_headers(df, WORK_ORDER_COLUMN_MAP)
    df = _standardize_sector(df)
    df = _apply_lowercase(df, WORK_ORDER_LOWERCASE_COLS)
    df = _cast_numeric(df, WORK_ORDER_NUMERIC_COLS)
    df = _drop_full_duplicates(df)
    return df