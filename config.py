import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")

# Monday.com endpoint
MONDAY_API_URL = "https://api.monday.com/v2"

# Board IDs (from monday.com board URLs)
DEALS_BOARD_ID = 5026937088
WORK_ORDERS_BOARD_ID = 5026937035


# ── Deal Funnel Board ────────────────────────────────────────────────────────
# Columns from the Sales Pipeline / Deal Funnel board

DEALS_COLUMNS = {
    "name":                 "name",
    "owner_code":           "text_mm12jqzj",
    "client_code":          "text_mm12gxwj",
    "deal_status":          "color_mm12bfrd",
    "close_date_actual":    "date_mm12bge4",
    "closure_probability":  "color_mm12ter0",
    "deal_value":           "numeric_mm1277vb",
    "tentative_close_date": "date_mm12xkvb",
    "deal_stage":           "color_mm12kjht",
    "product_deal":         "text_mm12qpbc",
    "sector":               "text_mm1242ka",
    "created_date":         "date_mm12bkg3",
}


# ── Work Orders Board ────────────────────────────────────────────────────────
# Columns from the Execution + Billing / Work Orders board

WORK_ORDER_COLUMNS = {
    "name":                    "name",
    "customer_code":           "text_mm123bmp",
    "serial_no":               "text_mm12dqyz",
    "nature_of_work":          "text_mm12yz5y",
    "last_recurring_month":    "text_mm12ay6s",
    "execution_status":        "color_mm12dz3z",
    "data_delivery_date":      "date_mm1267tz",
    "po_loi_date":             "date_mm126hwe",
    "document_type":           "text_mm12hvtr",
    "probable_start_date":     "date_mm128p4",
    "probable_end_date":       "date_mm122zvp",
    "bd_kam_code":             "text_mm12wsa3",
    "sector":                  "text_mm12gdk0",
    "type_of_work":            "text_mm128q6w",
    "skylark_platform":        "text_mm12hm6y",
    "last_invoice_date":       "date_mm12yhwd",
    "latest_invoice_no":       "text_mm126xdc",
    # Financials (all values are masked/scaled in source data)
    "amount_excl_gst":         "numeric_mm12m9fp",
    "amount_incl_gst":         "numeric_mm12efqb",
    "billed_excl_gst":         "numeric_mm12fpr3",
    "billed_incl_gst":         "numeric_mm12av2d",
    "collected_incl_gst":      "numeric_mm12g86c",
    "to_be_billed_excl_gst":   "numeric_mm12dtz9",
    "to_be_billed_incl_gst":   "numeric_mm12f6kn",
    "amount_receivable":       "numeric_mm12q54g",
    # Billing & collection tracking
    "ar_priority":             "text_mm124ckw",
    "qty_by_ops":              "numeric_mm12cq95",
    "qty_as_per_po":           "dropdown_mm128sfq",
    "qty_billed":              "numeric_mm128acf",
    "balance_qty":             "numeric_mm12jq2a",
    "invoice_status":          "color_mm129a8c",
    "expected_billing_month":  "text_mm12st92",
    "actual_billing_month":    "text_mm1284f8",
    "actual_collection_month": "text_mm12fngk",
    "wo_status":               "color_mm12f0f0",
    "collection_status":       "color_mm12yafv",
    "collection_date":         "text_mm12qjfy",
    "billing_status":          "color_mm12cew5",
}


# Column ID → Title lookups for header row detection
DEALS_COL_ID_TO_TITLE = {
    "name":               "Name",
    "text_mm12jqzj":      "Owner code",
    "text_mm12gxwj":      "Client Code",
    "color_mm12bfrd":     "Deal Status",
    "date_mm12bge4":      "Close Date (A)",
    "color_mm12ter0":     "Closure Probability",
    "numeric_mm1277vb":   "Masked Deal value",
    "date_mm12xkvb":      "Tentative Close Date",
    "color_mm12kjht":     "Deal Stage",
    "text_mm12qpbc":      "Product deal",
    "text_mm1242ka":      "Sector/service",
    "date_mm12bkg3":      "Created Date",
}

WORK_ORDER_COL_ID_TO_TITLE = {
    "name":                "Name",
    "text_mm123bmp":       "Customer Name Code",
    "text_mm12dqyz":       "Serial #",
    "text_mm12yz5y":       "Nature of Work",
    "text_mm12ay6s":       "Last executed month of recurring project",
    "color_mm12dz3z":      "Execution Status",
    "date_mm1267tz":       "Data Delivery Date",
    "date_mm126hwe":       "Date of PO/LOI",
    "text_mm12hvtr":       "Document Type",
    "date_mm128p4":        "Probable Start Date",
    "date_mm122zvp":       "Probable End Date",
    "text_mm12wsa3":       "BD/KAM Personnel code",
    "text_mm12gdk0":       "Sector",
    "text_mm128q6w":       "Type of Work",
    "text_mm12hm6y":       "Is any Skylark software platform part of the client deliverables in this deal?",
    "date_mm12yhwd":       "Last invoice date",
    "text_mm126xdc":       "latest invoice no.",
    "numeric_mm12m9fp":    "Amount in Rupees (Excl of GST) (Masked)",
    "numeric_mm12efqb":    "Amount in Rupees (Incl of GST) (Masked)",
    "numeric_mm12fpr3":    "Billed Value in Rupees (Excl of GST.) (Masked)",
    "numeric_mm12av2d":    "Billed Value in Rupees (Incl of GST.) (Masked)",
    "numeric_mm12g86c":    "Collected Amount in Rupees (Incl of GST.) (Masked)",
    "numeric_mm12dtz9":    "Amount to be billed in Rs. (Exl. of GST) (Masked)",
    "numeric_mm12f6kn":    "Amount to be billed in Rs. (Incl. of GST) (Masked)",
    "numeric_mm12q54g":    "Amount Receivable (Masked)",
    "text_mm124ckw":       "AR Priority account",
    "numeric_mm12cq95":    "Quantity by Ops",
    "dropdown_mm128sfq":   "Quantities as per PO",
    "numeric_mm128acf":    "Quantity billed (till date)",
    "numeric_mm12jq2a":    "Balance in quantity",
    "color_mm129a8c":      "Invoice Status",
    "text_mm12st92":       "Expected Billing Month",
    "text_mm1284f8":       "Actual Billing Month",
    "text_mm12fngk":       "Actual Collection Month",
    "color_mm12f0f0":      "WO Status (billed)",
    "color_mm12yafv":      "Collection status",
    "text_mm12qjfy":       "Collection Date",
    "color_mm12cew5":      "Billing Status",
}