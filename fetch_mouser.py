from __future__ import annotations

import os

import pandas as pd
import requests


API_KEY = os.getenv("MOUSER_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Error: MOUSER_API_KEY is not set. "
        "Please set it in your environment before running this script."
    )

# 件数が少ないときにすぐ調整できるよう環境変数で上書き可能
# 例:
# export MOUSER_KEYWORD="aluminum electrolytic capacitor"
# export MOUSER_MAX_RECORDS="300"
# export MOUSER_PAGE_SIZE="50"
KEYWORD = os.getenv("MOUSER_KEYWORD", "aluminum electrolytic capacitor")
MAX_RECORDS = int(os.getenv("MOUSER_MAX_RECORDS", "300"))
PAGE_SIZE = int(os.getenv("MOUSER_PAGE_SIZE", "50"))

if PAGE_SIZE <= 0:
    raise SystemExit("Error: MOUSER_PAGE_SIZE must be > 0")
if MAX_RECORDS <= 0:
    raise SystemExit("Error: MOUSER_MAX_RECORDS must be > 0")

URL = f"https://api.mouser.com/api/v1/search/keyword?apiKey={API_KEY}"


def extract_category(part: dict) -> str | None:
    """Mouserレスポンスからカテゴリを可能な範囲で抽出する。"""
    for key in ("Category", "CategoryName", "CategoryPath"):
        value = part.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for sub_key in ("Name", "CategoryName", "Value"):
                sub_value = value.get(sub_key)
                if isinstance(sub_value, str) and sub_value.strip():
                    return sub_value.strip()
    return None


def fetch_page(starting_record: int) -> list[dict]:
    """1ページ分のパーツ一覧を取得する。"""
    payload = {
        "SearchByKeywordRequest": {
            "keyword": KEYWORD,
            "records": PAGE_SIZE,
            "startingRecord": starting_record,
            "searchOptions": "",
            "searchWithYourSignUpLanguage": "false",
        }
    }
    response = requests.post(URL, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()
    search_results = data.get("SearchResults") or {}
    parts = search_results.get("Parts") or []
    return parts


rows: list[dict] = []
starting_record = 0
page = 1

while len(rows) < MAX_RECORDS:
    parts = fetch_page(starting_record)
    print(f"page {page}: fetched {len(parts)} records (start={starting_record})")

    if not parts:
        break

    for part in parts:
        price = None
        if part.get("PriceBreaks"):
            price = part["PriceBreaks"][0].get("Price")

        rows.append(
            {
                "part_number": part.get("ManufacturerPartNumber"),
                "manufacturer": part.get("Manufacturer"),
                "category": extract_category(part),
                "description": part.get("Description"),
                "availability": part.get("Availability"),
                "price": price,
                "datasheet_url": part.get("DataSheetUrl"),
                "product_url": part.get("ProductDetailUrl"),
            }
        )

        if len(rows) >= MAX_RECORDS:
            break

    # 返却件数がページサイズ未満なら最終ページとみなす
    if len(parts) < PAGE_SIZE:
        break

    starting_record += PAGE_SIZE
    page += 1

if not rows:
    raise SystemExit("No parts found. Try changing MOUSER_KEYWORD.")

df = pd.DataFrame(rows)

# 同一品番の重複があれば除去
before_dedup = len(df)
if "part_number" in df.columns:
    df = df.drop_duplicates(subset=["part_number"], keep="first")
after_dedup = len(df)

df.to_csv("capacitors.csv", index=False, encoding="utf-8-sig")
print(
    f"Saved capacitors.csv: {after_dedup} rows "
    f"(raw={before_dedup}, keyword='{KEYWORD}', max_records={MAX_RECORDS})"
)
