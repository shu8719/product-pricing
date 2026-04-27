from __future__ import annotations

import pandas as pd
import streamlit as st

from search_alternatives import (
    DEFAULT_PRODUCTION_QTY,
    build_alternative_table,
    find_original_part,
    load_clean_data,
)


def format_jpy(value: float | int | None) -> str:
    """Format number as JPY text used in UI."""
    if value is None or pd.isna(value):
        return "-"
    return f"JPY {float(value):,.2f}"


@st.cache_data
def get_clean_data() -> pd.DataFrame:
    """
    Read cleaned CSV only once per session.
    This avoids repeated file IO and keeps the app responsive.
    """
    return load_clean_data()


st.set_page_config(
    page_title="AI Parts Cross-Reference & Cost Optimizer",
    page_icon=":electric_plug:",
    layout="wide",
)

st.title("AI Parts Cross-Reference & Cost Optimizer")
st.caption("Local CSV mode: the app reads `capacitors_clean.csv` and does not call Mouser API.")

try:
    df = get_clean_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.info("Run `python clean_csv.py` first, then reload this page.")
    st.stop()

left, right = st.columns([2, 1])
with left:
    part_number = st.text_input(
        "Original Part Number",
        placeholder="Example: MAL214699805E3",
    ).strip()
with right:
    production_qty = st.number_input(
        "Production Quantity",
        min_value=1,
        value=DEFAULT_PRODUCTION_QTY,
        step=100,
    )

if not part_number:
    st.info("Enter a part number to search alternatives.")
    st.stop()

try:
    original = find_original_part(df, part_number)
except Exception as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Original Part")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Capacitance", f"{original['capacitance_uF']} uF")
col2.metric("Voltage", f"{original['voltage_V']} V")
col3.metric("Stock", f"{int(original['stock']) if pd.notna(original['stock']) else '-'}")
col4.metric("Unit Price", format_jpy(original["price_jpy"]))

original_info = pd.DataFrame(
    [
        {"Field": "Part Number", "Value": original["part_number"]},
        {"Field": "Manufacturer", "Value": original["manufacturer"]},
        {"Field": "Description", "Value": original["description"]},
        {"Field": "Product URL", "Value": original["product_url"]},
    ]
)
st.dataframe(original_info, hide_index=True, use_container_width=True)

if isinstance(original["product_url"], str) and original["product_url"].strip():
    st.markdown(f"[Open original product page]({original['product_url']})")

try:
    alternatives = build_alternative_table(
        df,
        original,
        production_qty=int(production_qty),
    )
except Exception as exc:
    st.error(f"Failed to build alternatives: {exc}")
    st.stop()

st.subheader("Alternative Ranking")
if alternatives.empty:
    st.warning("No alternatives found for the selected conditions.")
    st.stop()

top = alternatives.iloc[0]

summary_1, summary_2, summary_3 = st.columns(3)
summary_1.metric("Best Unit Price", format_jpy(top["price_jpy"]))
summary_2.metric("Unit Saving vs Original", format_jpy(top["unit_saving_jpy"]))
summary_3.metric(
    f"Saving for {int(production_qty):,} units",
    format_jpy(top["saving_for_lot_jpy"]),
)

ranking_columns = [
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
ranking = alternatives[ranking_columns].copy()

st.dataframe(
    ranking,
    hide_index=True,
    use_container_width=True,
    column_config={
        "part_number": "Part Number",
        "manufacturer": "Manufacturer",
        "capacitance_uF": st.column_config.NumberColumn("Capacitance (uF)", format="%.4g"),
        "voltage_V": st.column_config.NumberColumn("Voltage (V)", format="%.4g"),
        "stock": st.column_config.NumberColumn("Stock", format="%d"),
        "price_jpy": st.column_config.NumberColumn("Price (JPY)", format="%.2f"),
        "unit_saving_jpy": st.column_config.NumberColumn("Unit Saving (JPY)", format="%.2f"),
        "saving_rate_percent": st.column_config.NumberColumn("Saving Rate (%)", format="%.2f"),
        "saving_for_lot_jpy": st.column_config.NumberColumn(
            "Saving for Lot (JPY)", format="%.2f"
        ),
        "product_url": st.column_config.LinkColumn(
            "Product URL",
            display_text="Open",
        ),
    },
)
