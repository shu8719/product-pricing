from __future__ import annotations

from pathlib import Path

import pandas as pd

from catalog import (
    extract_capacitance_uf,
    extract_dimension_pair_mm,
    extract_lifetime_hours,
    extract_mount_type,
    extract_tolerance_percent,
    extract_voltage_v,
    is_aluminum_electrolytic_text,
    parse_price_jpy,
    parse_stock,
)


INPUT_CSV = Path("capacitors.csv")
OUTPUT_CSV = Path("capacitors_clean.csv")
REQUIRED_COLUMNS = {
    "part_number",
    "manufacturer",
    "description",
    "availability",
    "price",
    "datasheet_url",
    "product_url",
}


def is_target_aluminum_electrolytic(
    category_text: object,
    description_text: object,
) -> bool:
    """Category match first, then description fallback."""
    return is_aluminum_electrolytic_text(category_text) or is_aluminum_electrolytic_text(
        description_text
    )


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
    df["capacitance_uF"] = description_series.apply(extract_capacitance_uf)
    df["voltage_V"] = description_series.apply(extract_voltage_v)
    df["tolerance_percent"] = description_series.apply(extract_tolerance_percent)
    sizes = description_series.apply(extract_dimension_pair_mm)
    df["diameter_mm"] = [pair[0] for pair in sizes]
    df["height_mm"] = [pair[1] for pair in sizes]
    df["lifetime_hours"] = description_series.apply(extract_lifetime_hours)

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
    df["mount_type"] = df.apply(
        lambda row: extract_mount_type(row.get("category"), row.get("description")),
        axis=1,
    )

    # Make sure numeric columns are typed as numbers.
    df["capacitance_uF"] = pd.to_numeric(df["capacitance_uF"], errors="coerce")
    df["voltage_V"] = pd.to_numeric(df["voltage_V"], errors="coerce")
    df["tolerance_percent"] = pd.to_numeric(df["tolerance_percent"], errors="coerce")
    df["diameter_mm"] = pd.to_numeric(df["diameter_mm"], errors="coerce")
    df["height_mm"] = pd.to_numeric(df["height_mm"], errors="coerce")
    df["lifetime_hours"] = pd.to_numeric(df["lifetime_hours"], errors="coerce")
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
