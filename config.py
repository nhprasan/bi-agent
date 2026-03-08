"""
config.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API Keys & Endpoints
# ---------------------------------------------------------------------------

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"

# ---------------------------------------------------------------------------
# Monday.com Board IDs
# ---------------------------------------------------------------------------

DEALS_BOARD_ID       = 5026937088
WORK_ORDERS_BOARD_ID = 5026937035

# ---------------------------------------------------------------------------
# Column ID → snake_case name mappings
# Only columns used for analysis are kept here.
# Dropped from Work Orders: serial_number, document_type, type_of_work,
# ar_priority_account, billing_status, all quantity columns, all date columns,
# expected/actual billing month, collection_status, collection_date,
# last_executed_month, actual_collection_month, skylark_software_platform,
# last_invoice_date, latest_invoice_number.
# ---------------------------------------------------------------------------

DEAL_FUNNEL_COLUMN_MAP = {
    "text_mm12jqzj":    "owner_code",
    "text_mm12gxwj":    "client_code",
    "color_mm12bfrd":   "deal_status",
    "color_mm12ter0":   "closure_probability",
    "numeric_mm1277vb": "deal_value_masked",
    "color_mm12kjht":   "deal_stage",
    "text_mm12qpbc":    "product_deal",
    "text_mm1242ka":    "sector",
}

WORK_ORDER_COLUMN_MAP = {
    "text_mm123bmp":     "customer_name_code",
    "text_mm12yz5y":     "nature_of_work",
    "color_mm12dz3z":    "execution_status",
    "text_mm12wsa3":     "bd_kam_personnel_code",
    "text_mm12gdk0":     "sector",
    "numeric_mm12m9fp":  "amount_excl_gst_masked",
    "numeric_mm12efqb":  "amount_incl_gst_masked",
    "numeric_mm12fpr3":  "billed_value_excl_gst_masked",
    "numeric_mm12av2d":  "billed_value_incl_gst_masked",
    "numeric_mm12g86c":  "collected_amount_incl_gst_masked",
    "numeric_mm12dtz9":  "amount_to_be_billed_excl_gst_masked",
    "numeric_mm12f6kn":  "amount_to_be_billed_incl_gst_masked",
    "numeric_mm12q54g":  "amount_receivable_masked",
    "color_mm129a8c":    "invoice_status",
    "color_mm12f0f0":    "wo_status_billed",
}

# ---------------------------------------------------------------------------
# Numeric columns — cast to float so Pandas can aggregate them.
# ---------------------------------------------------------------------------

DEAL_NUMERIC_COLS = [
    "deal_value_masked",
]

WORK_ORDER_NUMERIC_COLS = [
    "amount_excl_gst_masked",
    "amount_incl_gst_masked",
    "billed_value_excl_gst_masked",
    "billed_value_incl_gst_masked",
    "collected_amount_incl_gst_masked",
    "amount_to_be_billed_excl_gst_masked",
    "amount_to_be_billed_incl_gst_masked",
    "amount_receivable_masked",
]

# ---------------------------------------------------------------------------
# Sector canonicalization — Deal Funnel is the source of truth.
# Work Order sector values get mapped to the same canonical names here.
# ---------------------------------------------------------------------------

SECTOR_CANONICAL = {
    "mining":                    "Mining",
    "powerline":                 "Powerline",
    "renewables":                "Renewables",
    "railways":                  "Railways",
    "construction":              "Construction",
    "others":                    "Others",
    "tender":                    "Tender",
    "dsp":                       "DSP",
    "aviation":                  "Aviation",
    "security and surveillance": "Security and Surveillance",
    "manufacturing":             "Manufacturing",
    "renewable":                 "Renewables",   # alternate spelling
    "railway":                   "Railways",     # alternate spelling
    "power line":                "Powerline",    # space variant
    "power-line":                "Powerline",    # hyphen variant
    "infra":                     "Construction", # shorthand
    "infrastructure":            "Construction", # full form
}

# ---------------------------------------------------------------------------
# Embedded header labels — Monday sometimes inserts group header rows as
# actual data items. Rows matching these labels get dropped in the normalizer.
# ---------------------------------------------------------------------------

KNOWN_HEADER_LABELS = {
    "deal name", "owner code", "client code", "deal status",
    "close date (a)", "closure probability", "masked deal value",
    "tentative close date", "deal stage", "product deal",
    "sector/service", "created date", "deal name masked",
    "customer name code", "nature of work", "execution status",
    "bd/kam personnel code", "invoice status", "wo status (billed)",
}

# ---------------------------------------------------------------------------
# Lowercase normalization — only categorical columns we do string comparisons on.
# ---------------------------------------------------------------------------

DEAL_LOWERCASE_COLS = [
    "deal_status",
    "closure_probability",
    "deal_stage",
    "product_deal",
    "sector",
]

WORK_ORDER_LOWERCASE_COLS = [
    "nature_of_work",
    "execution_status",
    "invoice_status",
    "wo_status_billed",
    "sector",
]

# ---------------------------------------------------------------------------
# Standard data quality column lists — passed to _count_missing in tools.py.
# Defined once here so individual tools don't each repeat the same lists.
# ---------------------------------------------------------------------------

DEALS_DQ_COLS = [
    "deal_value_masked",
    "deal_status",
    "sector",
    "owner_code",
]

WO_DQ_COLS = [
    "amount_excl_gst_masked",
    "billed_value_excl_gst_masked",
    "billed_value_incl_gst_masked",
    "collected_amount_incl_gst_masked",
    "amount_receivable_masked",
    "wo_status_billed",
    "execution_status",
    "invoice_status",
    "nature_of_work",
    "bd_kam_personnel_code",
]