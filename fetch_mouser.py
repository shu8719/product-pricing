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

# Narrow down at search time to reduce mixed capacitor types.
KEYWORD = "aluminum electrolytic capacitor 100uF"
URL = f"https://api.mouser.com/api/v1/search/keyword?apiKey={API_KEY}"
PAYLOAD = {
    "SearchByKeywordRequest": {
        "keyword": KEYWORD,
        "records": 50,
        "startingRecord": 0,
        "searchOptions": "",
        "searchWithYourSignUpLanguage": "false",
    }
}


def extract_category(part: dict) -> str | None:
    """Best-effort extraction for category text from Mouser API response."""
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


response = requests.post(URL, json=PAYLOAD, timeout=30)
print("status:", response.status_code)
response.raise_for_status()

data = response.json()
if not data.get("SearchResults"):
    raise SystemExit("No SearchResults in API response.")

parts = data["SearchResults"].get("Parts")
if not parts:
    raise SystemExit("No parts found in API response.")

rows = []
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

df = pd.DataFrame(rows)
df.to_csv("capacitors.csv", index=False, encoding="utf-8-sig")
print(f"Saved capacitors.csv ({len(df)} rows) with keyword: {KEYWORD}")
