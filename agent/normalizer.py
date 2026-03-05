# Generic data cleaning for Monday.com API responses.
# Functions here handle categories of problems (nulls, casing, numbers, header rows)

# Known sector aliases — lookup table because sector names are the primary grouping key used across both boards, and the two boards don't always spell them the same way.
SECTOR_ALIASES = {
    "mining":                    "Mining",
    "powerline":                 "Powerline",
    "renewables":                "Renewables",
    "railways":                  "Railways",
    "construction":              "Construction",
    "aviation":                  "Aviation",
    "dsp":                       "DSP",
    "manufacturing":             "Manufacturing",
    "tender":                    "Tender",
    "security and surveillance": "Security and Surveillance",
    "others":                    "Others",
    "other":                     "Others",
}


def normalize_sector(raw: str) -> str:
    """
    Returns a canonical sector name.
    Falls back to title-case of the raw value if not in the alias map.
    """
    if not raw or not raw.strip():
        return ""
    return SECTOR_ALIASES.get(raw.strip().lower(), raw.strip().title())


def clean_text(value) -> str:
    """
    Strips whitespace and normalizes empty/None to empty string.
    Use this for any text field before comparisons or display.
    """
    if value is None:
        return ""
    return str(value).strip()


# Canonical month mapping — handles both abbreviations and full names, case-insensitive.
_MONTH_MAP = {
    "jan": "January", "january": "January",
    "feb": "February", "february": "February",
    "mar": "March", "march": "March",
    "apr": "April", "april": "April",
    "may": "May",
    "jun": "June", "june": "June",
    "jul": "July", "july": "July",
    "aug": "August", "august": "August",
    "sep": "September", "sept": "September", "september": "September",
    "oct": "October", "october": "October",
    "nov": "November", "november": "November",
    "dec": "December", "december": "December",
}

def normalize_month(value) -> str:
    """
    Returns a canonical full month name from any abbreviated or
    full month string. Returns empty string if unrecognized.
    """
    cleaned = clean_text(value).strip().lower()
    if not cleaned:
        return ""
    # Strip year suffixes like "Dec-25" → "dec" or "January 2026" → "january"
    cleaned = cleaned.split("-")[0].split(" ")[0]
    return _MONTH_MAP.get(cleaned, clean_text(value).title())


def normalize_date(value) -> str | None:
    """
    Returns the date string as-is if present, None if empty.
    Monday.com returns dates as 'YYYY-MM-DD' strings already.
    """
    cleaned = clean_text(value)
    return cleaned if cleaned else None


def normalize_status(value: str) -> str:
    """
    Title-cases a status string and strips whitespace.
    Handles inconsistent casing across rows and boards, while preserving the original text otherwise.
    """
    cleaned = clean_text(value)
    return cleaned.title() if cleaned else ""


def to_float(value) -> float | None:
    """
    Converts a value to float. Returns None for missing/unparseable
    values so callers can distinguish between zero and unknown.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def is_header_row(item: dict, col_id_to_title: dict) -> bool:
    """
    Detects accidental Excel header rows imported as data rows.
    """
    flat = {
        col.get("id"): clean_text(col.get("text"))
        for col in item.get("column_values", [])
    }
    # Also include the item name field
    flat["name"] = clean_text(item.get("name", ""))

    matches = 0
    for col_id, title in col_id_to_title.items():
        cell_value = flat.get(col_id, "")
        if cell_value and cell_value.strip().lower() == title.strip().lower():
            matches += 1
    return matches >= 2


def parse_column_values(column_values: list, column_map: dict) -> dict:
    """
    Converts Monday.com's column_values list into a clean dict
    using the friendly key names defined in config.py.
    """
    id_to_key = {
        monday_id: friendly_key
        for friendly_key, monday_id in column_map.items()
        if friendly_key != "name"
    }

    result = {}
    for col in (column_values or []):
        col_id = col.get("id")
        col_text = clean_text(col.get("text"))
        friendly_key = id_to_key.get(col_id)
        if friendly_key:
            result[friendly_key] = col_text

    return result