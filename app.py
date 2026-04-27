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
    page_title="AI部品クロスリファレンス・価格最適化",
    page_icon=":electric_plug:",
    layout="wide",
)

st.title("AI部品クロスリファレンス・価格最適化")
st.caption(
    "ローカルCSVモード: `capacitors_clean.csv` を読み込み、Mouser APIは呼び出しません。"
)

try:
    df = get_clean_data()
except Exception as exc:
    st.error(f"データの読み込みに失敗しました: {exc}")
    st.info("先に `python clean_csv.py` を実行してから、このページを再読み込みしてください。")
    st.stop()

left, right = st.columns([2, 1])
with left:
    part_number = st.text_input(
        "元部品の品番",
        placeholder="例: MAL214699805E3",
    ).strip()
with right:
    production_qty = st.number_input(
        "生産数量",
        min_value=1,
        value=DEFAULT_PRODUCTION_QTY,
        step=100,
    )

if not part_number:
    st.info("代替候補を検索するには品番を入力してください。")
    st.stop()

try:
    original = find_original_part(df, part_number)
except Exception as exc:
    st.error(str(exc))
    st.stop()

st.subheader("元部品情報")

col1, col2, col3, col4 = st.columns(4)
col1.metric("容量", f"{original['capacitance_uF']} uF")
col2.metric("耐圧", f"{original['voltage_V']} V")
col3.metric("在庫数", f"{int(original['stock']) if pd.notna(original['stock']) else '-'}")
col4.metric("単価", format_jpy(original["price_jpy"]))

original_info = pd.DataFrame(
    [
        {"項目": "品番", "値": original["part_number"]},
        {"項目": "メーカー", "値": original["manufacturer"]},
        {"項目": "説明", "値": original["description"]},
        {"項目": "商品URL", "値": original["product_url"]},
    ]
)
st.dataframe(original_info, hide_index=True, use_container_width=True)

if isinstance(original["product_url"], str) and original["product_url"].strip():
    st.markdown(f"[元部品の商品ページを開く]({original['product_url']})")

try:
    alternatives = build_alternative_table(
        df,
        original,
        production_qty=int(production_qty),
    )
except Exception as exc:
    st.error(f"代替候補の作成に失敗しました: {exc}")
    st.stop()

st.subheader("代替候補ランキング")
if alternatives.empty:
    st.warning("指定した条件に一致する代替候補は見つかりませんでした。")
    st.stop()

top = alternatives.iloc[0]

summary_1, summary_2, summary_3 = st.columns(3)
summary_1.metric("最安単価", format_jpy(top["price_jpy"]))
summary_2.metric("元部品との差額（単価）", format_jpy(top["unit_saving_jpy"]))
summary_3.metric(
    f"{int(production_qty):,} 個生産時の削減額",
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
        "part_number": "品番",
        "manufacturer": "メーカー",
        "capacitance_uF": st.column_config.NumberColumn("容量 (uF)", format="%.4g"),
        "voltage_V": st.column_config.NumberColumn("耐圧 (V)", format="%.4g"),
        "stock": st.column_config.NumberColumn("在庫数", format="%d"),
        "price_jpy": st.column_config.NumberColumn("単価 (JPY)", format="%.2f"),
        "unit_saving_jpy": st.column_config.NumberColumn("単価差額 (JPY)", format="%.2f"),
        "saving_rate_percent": st.column_config.NumberColumn("削減率 (%)", format="%.2f"),
        "saving_for_lot_jpy": st.column_config.NumberColumn(
            "ロット削減額 (JPY)", format="%.2f"
        ),
        "product_url": st.column_config.LinkColumn(
            "商品URL",
            display_text="開く",
        ),
    },
)
