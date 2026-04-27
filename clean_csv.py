from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


# Input/output file names
INPUT_CSV = Path("capacitors.csv")
OUTPUT_CSV = Path("capacitors_clean.csv")

# Required columns in the original CSV
REQUIRED_COLUMNS = {
    "part_number",
    "manufacturer",
    "description",
    "availability",
    "price",
    "datasheet_url",
    "product_url",
}

# Regex patterns to parse values from description text.
# Allow variants such as uF / UF / MuF / mF before "F".
CAPACITANCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[A-Za-z]{0,2}\s*F\b", re.IGNORECASE
)
VOLTAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*V(?:DC)?\b", re.IGNORECASE)
TOLERANCE_PATTERN = re.compile(r"(?:\+/-)?\s*(\d+(?:\.\d+)?)\s*%")
NUMBER_PATTERN = re.compile(r"[\d,]+(?:\.\d+)?")
ALUMINUM_PATTERN = re.compile(r"(アルミ(?:ニウム)?|aluminium?)", re.IGNORECASE)
ELECTROLYTIC_PATTERN = re.compile(r"(電解|electrolytic)", re.IGNORECASE)


def extract_first_float(text: str, pattern: re.Pattern[str]) -> float | None:
    """Extract the first matching float from text using a regex pattern."""
    if not text:
        return None
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_price_jpy(price_text: object) -> float | None:
    """
    Convert strings like '¥2,526.5' to float (2526.5).
    Returns None when conversion is not possible.
    """
    if pd.isna(price_text):
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_text))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_stock(availability_text: object) -> int | None:
    """
    Convert strings like '7,716 In Stock' or '7716 在庫' to integer stock count.
    Returns None when conversion is not possible.
    """
    if pd.isna(availability_text):
        return None
    match = NUMBER_PATTERN.search(str(availability_text))
    if not match:
        return None

    number_text = match.group(0).replace(",", "")
    if not number_text:
        return None
    try:
        return int(float(number_text))
    except ValueError:
        return None


def is_aluminum_electrolytic_text(text: object) -> bool:
    """
    Return True when text includes BOTH aluminum and electrolytic keywords.
    Supports Japanese and English keywords.
    """
    if pd.isna(text):
        return False
    text_str = str(text)
    return bool(ALUMINUM_PATTERN.search(text_str) and ELECTROLYTIC_PATTERN.search(text_str))


def is_target_aluminum_electrolytic(category_text: object, description_text: object) -> bool:
    """
    Priority:
    1) category match (recommended when available)
    2) description match (fallback)
    """
    category_match = is_aluminum_electrolytic_text(category_text)
    description_match = is_aluminum_electrolytic_text(description_text)
    return category_match or description_match


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"Error: input file not found: {INPUT_CSV}")
        return 1

    try:
        df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    except Exception as exc:
        print(f"Error: failed to read {INPUT_CSV}: {exc}")
        return 1

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        print(f"Error: missing required columns: {sorted(missing)}")
        return 1

    # category is optional (newer fetch_mouser.py writes it).
    if "category" not in df.columns:
        df["category"] = pd.NA

    description_series = df["description"].fillna("")

    # Parse electrical specs from the free-text description.
    df["capacitance_uF"] = description_series.apply(
        lambda text: extract_first_float(text, CAPACITANCE_PATTERN)
    )
    df["voltage_V"] = description_series.apply(
        lambda text: extract_first_float(text, VOLTAGE_PATTERN)
    )
    df["tolerance_percent"] = description_series.apply(
        lambda text: extract_first_float(text, TOLERANCE_PATTERN)
    )

    # Parse text fields into numeric fields used by pricing logic.
    df["price_jpy"] = df["price"].apply(parse_price_jpy)
    df["stock"] = df["availability"].apply(parse_stock)
    df["is_aluminum_electrolytic"] = df.apply(
        lambda row: is_target_aluminum_electrolytic(
            row.get("category"),
            row.get("description"),
        ),
        axis=1,
    )

    # Make sure numeric columns are typed as numbers.
    df["capacitance_uF"] = pd.to_numeric(df["capacitance_uF"], errors="coerce")
    df["voltage_V"] = pd.to_numeric(df["voltage_V"], errors="coerce")
    df["tolerance_percent"] = pd.to_numeric(df["tolerance_percent"], errors="coerce")
    df["price_jpy"] = pd.to_numeric(df["price_jpy"], errors="coerce")
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").astype("Int64")

    # Keep only aluminum electrolytic capacitors.
    total_rows = len(df)
    df = df[df["is_aluminum_electrolytic"]].copy()
    filtered_rows = len(df)

    try:
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    except Exception as exc:
        print(f"Error: failed to write {OUTPUT_CSV}: {exc}")
        return 1

    print(
        f"Done: saved {OUTPUT_CSV} ({filtered_rows} rows, filtered from {total_rows})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
