from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUT_CSV = Path("capacitors_clean.csv")
CAPACITANCE_MATCH_TOLERANCE = 1e-9
DEFAULT_PRODUCTION_QTY = 10_000
REQUIRED_COLUMNS = {
    "part_number",
    "manufacturer",
    "description",
    "availability",
    "price",
    "price_jpy",
    "capacitance_uF",
    "voltage_V",
    "stock",
    "product_url",
}


def load_clean_data(path: Path = INPUT_CSV) -> pd.DataFrame:
    """Load and validate the cleaned capacitor CSV."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python clean_csv.py` first."
        )

    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in {path}: {sorted(missing)}"
        )

    # Ensure numeric columns are in numeric dtype.
    df["capacitance_uF"] = pd.to_numeric(df["capacitance_uF"], errors="coerce")
    df["voltage_V"] = pd.to_numeric(df["voltage_V"], errors="coerce")
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce")
    df["price_jpy"] = pd.to_numeric(df["price_jpy"], errors="coerce")
    return df


def find_original_part(df: pd.DataFrame, part_number: str) -> pd.Series:
    """Find the original part by exact part number (case-insensitive)."""
    normalized = part_number.strip().upper()
    if not normalized:
        raise ValueError("Part number is empty.")

    matched = df[df["part_number"].astype(str).str.upper() == normalized]
    if matched.empty:
        raise ValueError(f"Part number not found: {part_number}")
    return matched.iloc[0]


def build_alternative_table(
    df: pd.DataFrame,
    original_part: pd.Series,
    production_qty: int = DEFAULT_PRODUCTION_QTY,
) -> pd.DataFrame:
    """
    Search alternatives using these conditions:
    - same capacitance
    - voltage >= original voltage
    - stock > 0
    - exclude original part itself
    """
    required_for_search = ["capacitance_uF", "voltage_V", "price_jpy"]
    for col in required_for_search:
        if pd.isna(original_part[col]):
            raise ValueError(
                f"Original part has no usable `{col}` value. "
                "Please check the cleaned CSV."
            )

    original_part_number = str(original_part["part_number"]).upper()
    original_capacitance = float(original_part["capacitance_uF"])
    original_voltage = float(original_part["voltage_V"])
    original_price = float(original_part["price_jpy"])

    candidates = df.copy()
    candidates = candidates.dropna(
        subset=["capacitance_uF", "voltage_V", "stock", "price_jpy"]
    )
    candidates = candidates[
        (candidates["capacitance_uF"] - original_capacitance).abs()
        <= CAPACITANCE_MATCH_TOLERANCE
    ]
    candidates = candidates[candidates["voltage_V"] >= original_voltage]
    candidates = candidates[candidates["stock"] > 0]
    candidates = candidates[
        candidates["part_number"].astype(str).str.upper() != original_part_number
    ]

    if candidates.empty:
        return candidates

    candidates = candidates.sort_values("price_jpy", ascending=True).copy()

    # Positive value means this candidate is cheaper than the original.
    candidates["unit_saving_jpy"] = original_price - candidates["price_jpy"]
    candidates["saving_rate_percent"] = (
        candidates["unit_saving_jpy"] / original_price * 100
    )
    candidates["saving_for_lot_jpy"] = candidates["unit_saving_jpy"] * production_qty
    return candidates


def pretty_print_original(original: pd.Series) -> None:
    """Print base part information in CLI."""
    print("\n=== Original Part ===")
    print(f"Part Number   : {original['part_number']}")
    print(f"Manufacturer  : {original['manufacturer']}")
    print(f"Description   : {original['description']}")
    print(f"Capacitance   : {original['capacitance_uF']} uF")
    print(f"Voltage       : {original['voltage_V']} V")
    print(f"Stock         : {original['stock']}")
    print(f"Unit Price    : {original['price_jpy']} JPY")
    print(f"Product URL   : {original['product_url']}")


def main() -> int:
    try:
        df = load_clean_data()
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    user_input = input("Enter original part number: ").strip()
    if not user_input:
        print("Error: please enter a part number.")
        return 1

    try:
        original = find_original_part(df, user_input)
        pretty_print_original(original)
        alternatives = build_alternative_table(
            df, original, production_qty=DEFAULT_PRODUCTION_QTY
        )
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    if alternatives.empty:
        print("\nNo alternatives found for the selected conditions.")
        return 0

    display_columns = [
        "part_number",
        "manufacturer",
        "capacitance_uF",
        "voltage_V",
        "stock",
        "price_jpy",
        "unit_saving_jpy",
        "saving_rate_percent",
        "saving_for_lot_jpy",
        "product_url",
    ]
    result = alternatives[display_columns].copy()

    # Round values for readable CLI output.
    result["price_jpy"] = result["price_jpy"].round(2)
    result["unit_saving_jpy"] = result["unit_saving_jpy"].round(2)
    result["saving_rate_percent"] = result["saving_rate_percent"].round(2)
    result["saving_for_lot_jpy"] = result["saving_for_lot_jpy"].round(2)

    print(f"\n=== Alternative Ranking (lot size: {DEFAULT_PRODUCTION_QTY:,}) ===")
    print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
