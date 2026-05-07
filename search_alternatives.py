from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from catalog import load_combined_catalog, load_primary_catalog


INPUT_CSV = Path("capacitors_clean.csv")
DEFAULT_PRODUCTION_QTY = 10_000
CAPACITANCE_RELATIVE_TOLERANCE = 0.02
SIMILARITY_COLUMNS = [
    "voltage_V",
    "tolerance_percent",
    "diameter_mm",
    "height_mm",
    "lifetime_hours",
]


def load_clean_data(
    path: Path = INPUT_CSV,
    include_optional: bool = True,
) -> pd.DataFrame:
    """Load the cleaned catalog and optionally append local Digi-Key data."""
    if path != INPUT_CSV:
        return load_primary_catalog(path)
    return load_combined_catalog(include_optional=include_optional)


def find_original_part(df: pd.DataFrame, part_number: str) -> pd.Series:
    """Find the original part by exact part number (case-insensitive)."""
    normalized = part_number.strip().upper()
    if not normalized:
        raise ValueError("品番が空です。")

    matched = df[df["part_number"].astype(str).str.upper() == normalized]
    if matched.empty:
        raise ValueError(f"品番が見つかりません: {part_number}")
    return matched.iloc[0]


def _capacitance_mask(series: pd.Series, original_capacitance: float) -> pd.Series:
    tolerance = max(abs(original_capacitance) * CAPACITANCE_RELATIVE_TOLERANCE, 1e-9)
    return (series - original_capacitance).abs() <= tolerance


def _filter_candidates(
    df: pd.DataFrame,
    original_part: pd.Series,
    require_same_mount: bool,
) -> pd.DataFrame:
    original_part_number = str(original_part["part_number"]).upper()
    original_capacitance = float(original_part["capacitance_uF"])
    original_voltage = float(original_part["voltage_V"])
    original_tolerance = pd.to_numeric(
        pd.Series([original_part.get("tolerance_percent")]),
        errors="coerce",
    ).iloc[0]
    original_mount_type = original_part.get("mount_type")

    candidates = df.copy()
    candidates = candidates.dropna(
        subset=["capacitance_uF", "voltage_V", "stock", "price_jpy"]
    )
    candidates = candidates[candidates["stock"] > 0]
    candidates = candidates[
        candidates["part_number"].astype(str).str.upper() != original_part_number
    ]
    candidates = candidates[_capacitance_mask(candidates["capacitance_uF"], original_capacitance)]
    candidates = candidates[candidates["voltage_V"] >= original_voltage]

    if pd.notna(original_tolerance):
        candidates = candidates[
            candidates["tolerance_percent"].isna()
            | (candidates["tolerance_percent"] <= original_tolerance)
        ]

    if require_same_mount and isinstance(original_mount_type, str) and original_mount_type:
        candidates = candidates[candidates["mount_type"] == original_mount_type]

    return candidates.copy()


def _build_similarity_scores(
    candidates: pd.DataFrame,
    original_part: pd.Series,
) -> pd.DataFrame:
    scored = candidates.copy()
    original_price = float(original_part["price_jpy"])

    scored["unit_saving_jpy"] = original_price - scored["price_jpy"]
    scored["saving_rate_percent"] = scored["unit_saving_jpy"] / original_price * 100
    scored["is_cost_down"] = scored["unit_saving_jpy"] > 0

    available_columns = [
        column
        for column in SIMILARITY_COLUMNS
        if column in scored.columns and pd.notna(original_part.get(column))
    ]
    if available_columns:
        original_row = pd.DataFrame([{column: original_part.get(column) for column in available_columns}])
        feature_frame = pd.concat([original_row, scored[available_columns]], ignore_index=True)
        feature_frame = feature_frame.apply(pd.to_numeric, errors="coerce")
        feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True))
        scaled = StandardScaler().fit_transform(feature_frame)
        distances = np.linalg.norm(scaled[1:] - scaled[0], axis=1)
        scored["spec_distance"] = distances
    else:
        scored["spec_distance"] = 0.0

    max_distance = float(scored["spec_distance"].max()) if not scored.empty else 0.0
    if max_distance > 0:
        scored["distance_score"] = 1.0 - (scored["spec_distance"] / max_distance)
    else:
        scored["distance_score"] = 1.0

    stock_scale = np.log1p(scored["stock"].clip(lower=0))
    stock_max = float(stock_scale.max()) if not scored.empty else 0.0
    if stock_max > 0:
        scored["stock_score"] = stock_scale / stock_max
    else:
        scored["stock_score"] = 0.0

    positive_saving = scored["unit_saving_jpy"].clip(lower=0)
    max_positive_saving = float(positive_saving.max()) if not scored.empty else 0.0
    if max_positive_saving > 0:
        scored["saving_score"] = positive_saving / max_positive_saving
    else:
        scored["saving_score"] = 0.0

    same_mount = (
        scored["mount_type"].fillna("").astype(str)
        == str(original_part.get("mount_type") or "")
    )
    scored["mount_score"] = np.where(same_mount, 1.0, 0.5)

    scored["match_score"] = (
        scored["distance_score"] * 45
        + scored["saving_score"] * 35
        + scored["stock_score"] * 15
        + scored["mount_score"] * 5
    ).round(2)
    return scored


def build_alternative_table(
    df: pd.DataFrame,
    original_part: pd.Series,
    production_qty: int = DEFAULT_PRODUCTION_QTY,
) -> pd.DataFrame:
    """
    Build a ranked alternative table.

    The search first tries same-capacitance/same-mount candidates and falls back to a
    relaxed pool without the mount restriction when needed.
    """
    required_for_search = ["capacitance_uF", "voltage_V", "price_jpy"]
    for column in required_for_search:
        if pd.isna(original_part[column]):
            raise ValueError(
                f"元部品の `{column}` が欠損しています。clean後のCSVを確認してください。"
            )

    strict_pool = _filter_candidates(df, original_part, require_same_mount=True)
    compatibility_tier = "strict"
    candidates = strict_pool

    if candidates.empty:
        candidates = _filter_candidates(df, original_part, require_same_mount=False)
        compatibility_tier = "relaxed"

    if candidates.empty:
        return candidates

    ranked = _build_similarity_scores(candidates, original_part)
    ranked["saving_for_lot_jpy"] = ranked["unit_saving_jpy"] * production_qty
    ranked["compatibility_tier"] = compatibility_tier
    ranked = ranked.sort_values(
        by=["is_cost_down", "match_score", "unit_saving_jpy", "price_jpy"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    return ranked


def pretty_print_original(original: pd.Series) -> None:
    """Print base part information in CLI."""
    print("\n=== 元部品 ===")
    print(f"品番       : {original['part_number']}")
    print(f"メーカー   : {original['manufacturer']}")
    print(f"ソース     : {original.get('source', '-')}")
    print(f"説明       : {original['description']}")
    print(f"容量       : {original['capacitance_uF']} uF")
    print(f"耐圧       : {original['voltage_V']} V")
    print(f"在庫       : {original['stock']}")
    print(f"単価       : {original['price_jpy']} JPY")
    print(f"実装形態   : {original.get('mount_type', '-')}")
    print(f"商品URL    : {original['product_url']}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="代替部品検索 CLI")
    parser.add_argument("--part-number", help="元部品の品番")
    parser.add_argument(
        "--production-qty",
        type=int,
        default=DEFAULT_PRODUCTION_QTY,
        help="削減額計算に使う生産数量",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="digi.xlsx があれば検索対象に含める",
    )
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()

    try:
        df = load_clean_data(include_optional=args.include_optional)
    except Exception as exc:
        print(f"エラー: {exc}")
        return 1

    part_number = args.part_number
    if not part_number:
        part_number = input("元部品の品番を入力してください: ").strip()
    if not part_number:
        print("エラー: 品番を入力してください。")
        return 1

    try:
        original = find_original_part(df, part_number)
        pretty_print_original(original)
        alternatives = build_alternative_table(
            df,
            original,
            production_qty=args.production_qty,
        )
    except Exception as exc:
        print(f"エラー: {exc}")
        return 1

    if alternatives.empty:
        print("\n指定した条件に一致する代替候補は見つかりませんでした。")
        return 0

    display_columns = [
        "part_number",
        "manufacturer",
        "source",
        "mount_type",
        "capacitance_uF",
        "voltage_V",
        "stock",
        "price_jpy",
        "unit_saving_jpy",
        "saving_rate_percent",
        "saving_for_lot_jpy",
        "match_score",
        "compatibility_tier",
    ]
    result = alternatives[display_columns].copy()
    result["price_jpy"] = result["price_jpy"].round(2)
    result["unit_saving_jpy"] = result["unit_saving_jpy"].round(2)
    result["saving_rate_percent"] = result["saving_rate_percent"].round(2)
    result["saving_for_lot_jpy"] = result["saving_for_lot_jpy"].round(2)

    print(
        f"\n=== 代替候補ランキング（ロット数: {args.production_qty:,} / strict優先） ==="
    )
    print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
