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
# These map Monday.com's internal column IDs to readable names we use in code.
# If a column is added/renamed on the board, update the ID here.
# ---------------------------------------------------------------------------

DEAL_FUNNEL_COLUMN_MAP = {
    "text_mm12jqzj":    "owner_code",
    "text_mm12gxwj":    "client_code",
    "color_mm12bfrd":   "deal_status",
    "date_mm12bge4":    "close_date_actual",
    "color_mm12ter0":   "closure_probability",
    "numeric_mm1277vb": "deal_value_masked",
    "date_mm12xkvb":    "tentative_close_date",
    "color_mm12kjht":   "deal_stage",
    "text_mm12qpbc":    "product_deal",
    "text_mm1242ka":    "sector",
    "date_mm12bkg3":    "created_date",
}

WORK_ORDER_COLUMN_MAP = {
    "text_mm123bmp":     "customer_name_code",
    "text_mm12dqyz":     "serial_number",
    "text_mm12yz5y":     "nature_of_work",
    "text_mm12ay6s":     "last_executed_month",
    "color_mm12dz3z":    "execution_status",
    "date_mm1267tz":     "data_delivery_date",
    "date_mm126hwe":     "date_of_po_loi",
    "text_mm12hvtr":     "document_type",
    "date_mm128p4":      "probable_start_date",
    "date_mm122zvp":     "probable_end_date",
    "text_mm12wsa3":     "bd_kam_personnel_code",
    "text_mm12gdk0":     "sector",
    "text_mm128q6w":     "type_of_work",
    "text_mm12hm6y":     "skylark_software_platform",
    "date_mm12yhwd":     "last_invoice_date",
    "text_mm126xdc":     "latest_invoice_number",
    "numeric_mm12m9fp":  "amount_excl_gst_masked",
    "numeric_mm12efqb":  "amount_incl_gst_masked",
    "numeric_mm12fpr3":  "billed_value_excl_gst_masked",
    "numeric_mm12av2d":  "billed_value_incl_gst_masked",
    "numeric_mm12g86c":  "collected_amount_incl_gst_masked",
    "numeric_mm12dtz9":  "amount_to_be_billed_excl_gst_masked",
    "numeric_mm12f6kn":  "amount_to_be_billed_incl_gst_masked",
    "numeric_mm12q54g":  "amount_receivable_masked",
    "text_mm124ckw":     "ar_priority_account",
    "numeric_mm12cq95":  "quantity_by_ops",       # kept as text (mixed units)
    "dropdown_mm128sfq": "quantities_as_per_po",  # kept as text (mixed units)
    "numeric_mm128acf":  "quantity_billed_till_date",
    "numeric_mm12jq2a":  "balance_in_quantity",
    "color_mm129a8c":    "invoice_status",
    "text_mm12st92":     "expected_billing_month",
    "text_mm1284f8":     "actual_billing_month",
    "text_mm12fngk":     "actual_collection_month",
    "color_mm12f0f0":    "wo_status_billed",
    "color_mm12yafv":    "collection_status",
    "text_mm12qjfy":     "collection_date",
    "color_mm12cew5":    "billing_status",
}

# ---------------------------------------------------------------------------
# Numeric columns — cast to float for aggregation.
# quantity_by_ops and quantities_as_per_po intentionally excluded (mixed units).
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
    "quantity_billed_till_date",
    "balance_in_quantity",
]

# ---------------------------------------------------------------------------
# Sector canonicalization — Deal Funnel is source of truth.
# Variants found in Work Orders get mapped to the canonical form here.
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
# Embedded header labels — rows whose values look like column headers get dropped.
# Monday sometimes exports header rows as data rows inside group items.
# ---------------------------------------------------------------------------

KNOWN_HEADER_LABELS = {
    "deal name", "owner code", "client code", "deal status",
    "close date (a)", "closure probability", "masked deal value",
    "tentative close date", "deal stage", "product deal",
    "sector/service", "created date", "deal name masked",
    "customer name code", "serial #", "nature of work",
    "execution status", "date of po/loi", "document type",
    "bd/kam personnel code",
}

# ---------------------------------------------------------------------------
# Lowercase normalization — applied to categorical/status columns only.
# Keeps comparisons consistent (e.g. "Open" == "open").
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
    "document_type",
    "skylark_software_platform",
    "type_of_work",
    "invoice_status",
    "wo_status_billed",
    "collection_status",
    "billing_status",
    "sector",
    "ar_priority_account",
]