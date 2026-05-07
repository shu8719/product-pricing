from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


PRIMARY_CSV = Path("capacitors_clean.csv")
OPTIONAL_DIGIKEY_PATHS = (Path("digi.xlsx"), Path("../digi.xlsx"))

PRIMARY_REQUIRED_COLUMNS = {
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
CANONICAL_COLUMNS = [
    "part_number",
    "manufacturer",
    "description",
    "availability",
    "price",
    "price_jpy",
    "datasheet_url",
    "product_url",
    "category",
    "source",
    "capacitance_uF",
    "voltage_V",
    "tolerance_percent",
    "stock",
    "diameter_mm",
    "height_mm",
    "lifetime_hours",
    "mount_type",
]
NUMERIC_COLUMNS = [
    "price_jpy",
    "capacitance_uF",
    "voltage_V",
    "tolerance_percent",
    "stock",
    "diameter_mm",
    "height_mm",
    "lifetime_hours",
]

CAPACITANCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[uμµm]?\s*F)\b",
    re.IGNORECASE,
)
VOLTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:V(?:DC)?|Volt(?:s)?)",
    re.IGNORECASE,
)
TOLERANCE_PATTERN = re.compile(r"(?:±|\+/-)?\s*(\d+(?:\.\d+)?)\s*%")
NUMBER_PATTERN = re.compile(r"[\d,]+(?:\.\d+)?")
SIZE_PAIR_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)(?:\s*mm)?",
    re.IGNORECASE,
)
MM_IN_PARENS_PATTERN = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*mm\s*[)）]", re.IGNORECASE)
MM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*mm\b", re.IGNORECASE)
LIFETIME_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:h(?:ours?)?|時間)", re.IGNORECASE)
ALUMINUM_PATTERN = re.compile(r"(アルミ(?:ニウム)?|aluminium?)", re.IGNORECASE)
ELECTROLYTIC_PATTERN = re.compile(r"(電解|electrolytic)", re.IGNORECASE)
MOUNT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("smd", re.compile(r"(smd|smt|surface\s*mount|chip)", re.IGNORECASE)),
    ("snap_in", re.compile(r"(snap[\s-]?in|スナップイン)", re.IGNORECASE)),
    ("screw", re.compile(r"(screw|ネジ端子)", re.IGNORECASE)),
    ("axial", re.compile(r"(axial|アキシャル)", re.IGNORECASE)),
    ("radial", re.compile(r"(radial|ラジアル)", re.IGNORECASE)),
)


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def extract_first_float(value: object, pattern: re.Pattern[str]) -> float | None:
    text = _text(value)
    if not text:
        return None
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_price_jpy(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_stock(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    match = NUMBER_PATTERN.search(text)
    if not match:
        return None
    number_text = match.group(0).replace(",", "")
    if not number_text:
        return None
    try:
        return int(float(number_text))
    except ValueError:
        return None


def extract_capacitance_uf(value: object) -> float | None:
    return extract_first_float(value, CAPACITANCE_PATTERN)


def extract_voltage_v(value: object) -> float | None:
    return extract_first_float(value, VOLTAGE_PATTERN)


def extract_tolerance_percent(value: object) -> float | None:
    return extract_first_float(value, TOLERANCE_PATTERN)


def extract_lifetime_hours(value: object) -> float | None:
    return extract_first_float(value, LIFETIME_PATTERN)


def extract_mm_value(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None

    match = MM_IN_PARENS_PATTERN.search(text)
    if match:
        return float(match.group(1))

    match = MM_PATTERN.search(text)
    if match:
        return float(match.group(1))
    return None


def extract_dimension_pair_mm(value: object) -> tuple[float | None, float | None]:
    text = _text(value)
    if not text:
        return None, None

    match = SIZE_PAIR_PATTERN.search(text)
    if not match:
        return None, None

    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None, None


def extract_mount_type(*values: object) -> str | None:
    joined = " ".join(_text(value) for value in values if _text(value))
    if not joined:
        return None

    for mount_type, pattern in MOUNT_PATTERNS:
        if pattern.search(joined):
            return mount_type
    return None


def is_aluminum_electrolytic_text(value: object) -> bool:
    text = _text(value)
    if not text:
        return False
    return bool(ALUMINUM_PATTERN.search(text) and ELECTROLYTIC_PATTERN.search(text))


def _ensure_column(df: pd.DataFrame, name: str, default: object = pd.NA) -> None:
    if name not in df.columns:
        df[name] = default


def enrich_primary_catalog(df: pd.DataFrame, source: str = "Mouser") -> pd.DataFrame:
    enriched = df.copy()

    _ensure_column(enriched, "source", source)
    _ensure_column(enriched, "datasheet_url")
    _ensure_column(enriched, "category")

    if "capacitance_uF" not in enriched.columns:
        enriched["capacitance_uF"] = enriched["description"].apply(extract_capacitance_uf)
    else:
        enriched["capacitance_uF"] = enriched["capacitance_uF"].fillna(
            enriched["description"].apply(extract_capacitance_uf)
        )
    if "voltage_V" not in enriched.columns:
        enriched["voltage_V"] = enriched["description"].apply(extract_voltage_v)
    else:
        enriched["voltage_V"] = enriched["voltage_V"].fillna(
            enriched["description"].apply(extract_voltage_v)
        )
    if "tolerance_percent" not in enriched.columns:
        enriched["tolerance_percent"] = enriched["description"].apply(
            extract_tolerance_percent
        )
    else:
        enriched["tolerance_percent"] = enriched["tolerance_percent"].fillna(
            enriched["description"].apply(extract_tolerance_percent)
        )
    if "price_jpy" not in enriched.columns:
        enriched["price_jpy"] = enriched["price"].apply(parse_price_jpy)
    if "stock" not in enriched.columns:
        enriched["stock"] = enriched["availability"].apply(parse_stock)

    sizes = enriched["description"].apply(extract_dimension_pair_mm)
    parsed_diameter = pd.Series([pair[0] for pair in sizes], index=enriched.index)
    parsed_height = pd.Series([pair[1] for pair in sizes], index=enriched.index)
    if "diameter_mm" not in enriched.columns:
        enriched["diameter_mm"] = parsed_diameter
    else:
        enriched["diameter_mm"] = enriched["diameter_mm"].fillna(parsed_diameter)
    if "height_mm" not in enriched.columns:
        enriched["height_mm"] = parsed_height
    else:
        enriched["height_mm"] = enriched["height_mm"].fillna(parsed_height)

    if "lifetime_hours" not in enriched.columns:
        enriched["lifetime_hours"] = enriched["description"].apply(extract_lifetime_hours)
    else:
        enriched["lifetime_hours"] = enriched["lifetime_hours"].fillna(
            enriched["description"].apply(extract_lifetime_hours)
        )

    parsed_mount_type = enriched.apply(
        lambda row: extract_mount_type(row.get("category"), row.get("description")),
        axis=1,
    )
    if "mount_type" not in enriched.columns:
        enriched["mount_type"] = parsed_mount_type
    else:
        enriched["mount_type"] = enriched["mount_type"].fillna(parsed_mount_type)

    for column in NUMERIC_COLUMNS:
        if column in enriched.columns:
            enriched[column] = pd.to_numeric(enriched[column], errors="coerce")

    for column in CANONICAL_COLUMNS:
        _ensure_column(enriched, column)
    return enriched[CANONICAL_COLUMNS].copy()


def load_primary_catalog(path: Path = PRIMARY_CSV) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} が見つかりません。先に `python clean_csv.py` を実行してください。"
        )

    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = PRIMARY_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{path} に必要な列が不足しています: {sorted(missing)}")
    return enrich_primary_catalog(df, source="Mouser")


def find_optional_digikey_file() -> Path | None:
    for path in OPTIONAL_DIGIKEY_PATHS:
        if path.exists():
            return path
    return None


def _join_text_parts(parts: list[object]) -> str:
    return " / ".join(_text(part) for part in parts if _text(part))


def load_optional_digikey_catalog(path: Path | None = None) -> pd.DataFrame:
    digikey_path = path or find_optional_digikey_file()
    if digikey_path is None:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    raw = pd.read_excel(digikey_path)
    required = {
        "メーカー品番",
        "メーカー",
        "在庫",
        "価格",
        "静電容量",
        "許容誤差",
        "電圧 - 定格",
        "寿命 @ 温度",
        "サイズ/寸法",
        "高さ - 座高（最大）",
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(
            f"{digikey_path} に必要な列が不足しています: {sorted(missing)}"
        )

    df = pd.DataFrame(
        {
            "part_number": raw["メーカー品番"],
            "manufacturer": raw["メーカー"],
            "description": raw.apply(
                lambda row: _join_text_parts(
                    [
                        "DigiKey",
                        row.get("シリーズ"),
                        row.get("静電容量"),
                        row.get("許容誤差"),
                        row.get("電圧 - 定格"),
                        row.get("寿命 @ 温度"),
                        row.get("サイズ/寸法"),
                        row.get("高さ - 座高（最大）"),
                    ]
                ),
                axis=1,
            ),
            "availability": raw["在庫"].apply(lambda value: f"{value} In Stock"),
            "price": raw["価格"],
            "price_jpy": raw["価格"].apply(parse_price_jpy),
            "datasheet_url": pd.NA,
            "product_url": pd.NA,
            "category": "アルミ電解コンデンサ",
            "source": "DigiKey",
            "capacitance_uF": raw["静電容量"].apply(extract_capacitance_uf),
            "voltage_V": raw["電圧 - 定格"].apply(extract_voltage_v),
            "tolerance_percent": raw["許容誤差"].apply(extract_tolerance_percent),
            "stock": raw["在庫"].apply(parse_stock),
            "diameter_mm": raw["サイズ/寸法"].apply(extract_mm_value),
            "height_mm": raw["高さ - 座高（最大）"].apply(extract_mm_value),
            "lifetime_hours": raw["寿命 @ 温度"].apply(extract_lifetime_hours),
            "mount_type": raw.apply(
                lambda row: extract_mount_type(
                    row.get("シリーズ"),
                    row.get("用途"),
                    row.get("サイズ/寸法"),
                ),
                axis=1,
            ),
        }
    )

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df[CANONICAL_COLUMNS].copy()


def load_combined_catalog(include_optional: bool = True) -> pd.DataFrame:
    frames = [load_primary_catalog()]
    if include_optional:
        optional = load_optional_digikey_catalog()
        if not optional.empty:
            frames.append(optional)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["source", "part_number"], keep="first")
    return combined.reset_index(drop=True)
