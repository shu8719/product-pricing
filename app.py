from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis_models import predict_price, train_price_model
from catalog import find_optional_digikey_file
from search_alternatives import (
    DEFAULT_PRODUCTION_QTY,
    build_alternative_table,
    find_original_part,
    load_clean_data,
)


def format_jpy(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"JPY {float(value):,.2f}"


def format_float(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def format_signed(value: object, digits: int = 2, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    return f"{number:+,.{digits}f}{suffix}"


def render_compact_metrics(columns, items: list[tuple[str, str]]) -> None:
    for column, (label, value) in zip(columns, items):
        column.metric(label, value)


@st.cache_data
def get_catalog() -> pd.DataFrame:
    return load_clean_data(include_optional=True)


@st.cache_resource
def get_price_model():
    return train_price_model(get_catalog())


st.set_page_config(
    page_title="AI部品クロスリファレンス・価格最適化",
    page_icon=":electric_plug:",
    layout="wide",
)

st.markdown(
    """
    <style>
    html {
        font-size: clamp(14px, 0.82vw, 17px);
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    h1 {
        font-size: clamp(1.55rem, 2.6vw, 2.45rem) !important;
        line-height: 1.08 !important;
    }
    h2 {
        font-size: clamp(1.2rem, 1.7vw, 1.65rem) !important;
        line-height: 1.18 !important;
    }
    h3 {
        font-size: clamp(1.02rem, 1.25vw, 1.25rem) !important;
        line-height: 1.22 !important;
    }
    p,
    label,
    li,
    .stCaption,
    .stMarkdown,
    .stAlert,
    .stTextInput label,
    .stNumberInput label,
    .stSlider label,
    .stCheckbox label,
    .stSelectbox label {
        font-size: clamp(0.86rem, 0.95vw, 0.98rem) !important;
        line-height: 1.35 !important;
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: clamp(0.8rem, 0.95vw, 0.98rem) !important;
        white-space: normal !important;
        line-height: 1.2 !important;
        min-height: 2.5rem;
    }
    div[data-testid="stMetric"] {
        background: #f6f8fb;
        border: 1px solid #e5eaf1;
        border-radius: 12px;
        padding: 0.45rem 0.7rem;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: clamp(0.72rem, 0.88vw, 0.9rem) !important;
        line-height: 1.2 !important;
        overflow-wrap: anywhere;
    }
    div[data-testid="stMetricValue"] {
        font-size: clamp(0.96rem, 1.45vw, 1.35rem) !important;
        line-height: 1.1 !important;
        overflow-wrap: anywhere;
    }
    [data-testid="stLinkButton"] a,
    [data-testid="stButton"] button {
        font-size: clamp(0.82rem, 0.95vw, 0.96rem) !important;
    }
    @media (max-width: 980px) {
        .block-container {
            padding-top: 0.75rem;
            padding-bottom: 0.75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AI部品クロスリファレンス・価格最適化")

optional_digikey_path = find_optional_digikey_file()
source_note = "Mouser"
if optional_digikey_path is not None:
    source_note = f"Mouser + DigiKey ({optional_digikey_path.name})"
st.caption(f"ローカルCSVモード: `{source_note}` のデータを読み込みます。")

try:
    catalog_df = get_catalog()
except Exception as exc:
    st.error(f"データの読み込みに失敗しました: {exc}")
    st.info(
        "先に `python clean_csv.py` を実行してください。追加で `digi.xlsx` があれば自動で読み込みます。"
    )
    st.stop()

summary_1, summary_2, summary_3 = st.columns(3)
summary_1.metric("検索対象部品数", f"{len(catalog_df):,}")
summary_2.metric("メーカー数", f"{catalog_df['manufacturer'].nunique():,}")
summary_3.metric("データソース", ", ".join(sorted(catalog_df["source"].dropna().unique())))

search_tab, price_tab = st.tabs(
    ["代替部品検索", "価格予測（簡易版）"]
)

with search_tab:
    search_left, search_right = st.columns([1.1, 1.9], gap="large")
    with search_left:
        st.subheader("検索条件")
        part_number = st.text_input(
            "元部品の品番",
            placeholder="例: MAL214699805E3",
        ).strip()
        production_qty = st.number_input(
            "生産数量",
            min_value=1,
            value=DEFAULT_PRODUCTION_QTY,
            step=100,
        )
        top_n = st.slider("表示件数", min_value=5, max_value=20, value=8)
        show_cost_down_only = st.checkbox("価格が下がる候補を優先表示", value=True)

        if not part_number:
            st.info("代替候補を検索するには品番を入力してください。")
        else:
            try:
                original = find_original_part(catalog_df, part_number)
                alternatives = build_alternative_table(
                    catalog_df,
                    original,
                    production_qty=int(production_qty),
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                render_compact_metrics(
                    st.columns(2),
                    [
                        ("容量", f"{format_float(original['capacitance_uF'])} uF"),
                        ("耐圧", f"{format_float(original['voltage_V'])} V"),
                    ],
                )
                render_compact_metrics(
                    st.columns(2),
                    [
                        (
                            "在庫数",
                            f"{int(original['stock']):,}"
                            if pd.notna(original["stock"])
                            else "-",
                        ),
                        ("単価", format_jpy(original["price_jpy"])),
                    ],
                )
                st.caption(
                    f"メーカー: {original['manufacturer']} / 実装形態: {original.get('mount_type') or '-'} / ソース: {original.get('source') or '-'}"
                )
                if isinstance(original["product_url"], str) and original["product_url"]:
                    st.link_button("元部品ページ", original["product_url"], use_container_width=True)
                with st.expander("元部品の詳細", expanded=False):
                    original_info = pd.DataFrame(
                        [
                            {"項目": "品番", "値": original["part_number"]},
                            {"項目": "メーカー", "値": original["manufacturer"]},
                            {"項目": "実装形態", "値": original.get("mount_type") or "-"},
                            {"項目": "説明", "値": original["description"]},
                        ]
                    )
                    st.dataframe(
                        original_info,
                        hide_index=True,
                        use_container_width=True,
                        height=180,
                    )

    with search_right:
        st.subheader("検索結果")
        if part_number:
            if "alternatives" in locals() and alternatives is not None and not alternatives.empty:
                cheaper = alternatives[alternatives["is_cost_down"]].copy()
                ranking = cheaper if show_cost_down_only and not cheaper.empty else alternatives
                ranking = ranking.head(top_n).copy()

                if cheaper.empty:
                    st.warning(
                        "互換候補は見つかりましたが、現在のデータではコストダウン候補はありません。"
                    )

                best = ranking.iloc[0]
                render_compact_metrics(
                    st.columns(3),
                    [
                        ("推奨候補", str(best["part_number"])),
                        ("単価差額", format_jpy(best["unit_saving_jpy"])),
                        (
                            "ロット削減額",
                            format_jpy(best["saving_for_lot_jpy"]),
                        ),
                    ],
                )
                render_compact_metrics(
                    st.columns(5),
                    [
                        ("容量誤差", f"{format_float(best['capacitance_error_percent'])}%"),
                        ("耐圧余裕", format_signed(best["voltage_margin_V"], suffix=" V")),
                        ("許容差余裕", format_signed(best["tolerance_margin_percent"], suffix="%")),
                        ("直径余裕", format_signed(best["diameter_margin_mm"], suffix=" mm")),
                        ("高さ余裕", format_signed(best["height_margin_mm"], suffix=" mm")),
                    ],
                )
                st.caption(
                    "検索モード: "
                    + (
                        "strict"
                        if str(best["compatibility_tier"]) == "strict"
                        else "relaxed"
                    )
                    + f" / ロット数: {int(production_qty):,}"
                )

                chart_col, table_col = st.columns([1.0, 1.45], gap="medium")
                with chart_col:
                    chart_df = ranking.copy()
                    chart_df["label"] = chart_df["part_number"].astype(str)
                    saving_chart = px.bar(
                        chart_df,
                        x="label",
                        y="saving_for_lot_jpy",
                        color="source",
                        title="ロット削減額",
                        labels={
                            "label": "候補",
                            "saving_for_lot_jpy": "削減額 (JPY)",
                            "source": "ソース",
                        },
                    )
                    saving_chart.update_layout(
                        xaxis_tickangle=-20,
                        height=290,
                        margin=dict(l=10, r=10, t=40, b=10),
                    )
                    st.plotly_chart(saving_chart, use_container_width=True)

                with table_col:
                    ranking_columns = [
                        "part_number",
                        "manufacturer",
                        "source",
                        "mount_type",
                        "price_jpy",
                        "unit_saving_jpy",
                        "saving_for_lot_jpy",
                        "capacitance_error_percent",
                        "voltage_margin_V",
                        "tolerance_margin_percent",
                        "diameter_margin_mm",
                        "height_margin_mm",
                    ]
                    st.dataframe(
                        ranking[ranking_columns],
                        hide_index=True,
                        use_container_width=True,
                        height=320,
                        column_config={
                            "part_number": "品番",
                            "manufacturer": "メーカー",
                            "source": "ソース",
                            "mount_type": "実装形態",
                            "price_jpy": st.column_config.NumberColumn(
                                "単価 (JPY)", format="%.2f"
                            ),
                            "unit_saving_jpy": st.column_config.NumberColumn(
                                "単価差額", format="%.2f"
                            ),
                            "saving_for_lot_jpy": st.column_config.NumberColumn(
                                "ロット削減額", format="%.2f"
                            ),
                            "capacitance_error_percent": st.column_config.NumberColumn(
                                "容量誤差 (%)", format="%.2f"
                            ),
                            "voltage_margin_V": st.column_config.NumberColumn(
                                "耐圧余裕 (V)", format="%.2f"
                            ),
                            "tolerance_margin_percent": st.column_config.NumberColumn(
                                "許容差余裕 (%)", format="%.2f"
                            ),
                            "diameter_margin_mm": st.column_config.NumberColumn(
                                "直径余裕 (mm)", format="%.2f"
                            ),
                            "height_margin_mm": st.column_config.NumberColumn(
                                "高さ余裕 (mm)", format="%.2f"
                            ),
                        },
                    )
                    with st.expander("候補の詳細列", expanded=False):
                        st.dataframe(
                            ranking[
                                [
                                    "part_number",
                                    "manufacturer",
                                    "source",
                                    "mount_type",
                                    "capacitance_uF",
                                    "capacitance_delta_uF",
                                    "capacitance_error_percent",
                                    "voltage_V",
                                    "voltage_margin_V",
                                    "tolerance_percent",
                                    "tolerance_margin_percent",
                                    "diameter_mm",
                                    "diameter_margin_mm",
                                    "height_mm",
                                    "height_margin_mm",
                                    "stock",
                                    "price_jpy",
                                    "unit_saving_jpy",
                                    "saving_rate_percent",
                                    "saving_for_lot_jpy",
                                    "product_url",
                                ]
                            ],
                            hide_index=True,
                            use_container_width=True,
                            height=220,
                            column_config={
                                "part_number": "品番",
                                "manufacturer": "メーカー",
                                "source": "ソース",
                                "mount_type": "実装形態",
                                "capacitance_uF": st.column_config.NumberColumn(
                                    "容量", format="%.4g"
                                ),
                                "capacitance_delta_uF": st.column_config.NumberColumn(
                                    "容量差 (uF)", format="%.4f"
                                ),
                                "capacitance_error_percent": st.column_config.NumberColumn(
                                    "容量誤差 (%)", format="%.2f"
                                ),
                                "voltage_V": st.column_config.NumberColumn(
                                    "耐圧", format="%.4g"
                                ),
                                "voltage_margin_V": st.column_config.NumberColumn(
                                    "耐圧余裕 (V)", format="%.2f"
                                ),
                                "tolerance_percent": st.column_config.NumberColumn(
                                    "許容差 (%)", format="%.2f"
                                ),
                                "tolerance_margin_percent": st.column_config.NumberColumn(
                                    "許容差余裕 (%)", format="%.2f"
                                ),
                                "diameter_mm": st.column_config.NumberColumn(
                                    "直径 (mm)", format="%.2f"
                                ),
                                "diameter_margin_mm": st.column_config.NumberColumn(
                                    "直径余裕 (mm)", format="%.2f"
                                ),
                                "height_mm": st.column_config.NumberColumn(
                                    "高さ (mm)", format="%.2f"
                                ),
                                "height_margin_mm": st.column_config.NumberColumn(
                                    "高さ余裕 (mm)", format="%.2f"
                                ),
                                "stock": st.column_config.NumberColumn("在庫数", format="%d"),
                                "price_jpy": st.column_config.NumberColumn(
                                    "単価", format="%.2f"
                                ),
                                "unit_saving_jpy": st.column_config.NumberColumn(
                                    "単価差額", format="%.2f"
                                ),
                                "saving_rate_percent": st.column_config.NumberColumn(
                                    "削減率", format="%.2f"
                                ),
                                "saving_for_lot_jpy": st.column_config.NumberColumn(
                                    "ロット削減額", format="%.2f"
                                ),
                                "product_url": st.column_config.LinkColumn(
                                    "商品URL", display_text="開く"
                                ),
                            },
                        )
            elif "alternatives" in locals() and alternatives is not None and alternatives.empty:
                st.warning("指定した条件に一致する代替候補は見つかりませんでした。")

with price_tab:
    st.caption("現行データから単価を回帰する簡易モデルです。発表では参考値として扱う想定です。")
    try:
        price_model = get_price_model()
    except Exception as exc:
        st.error(f"価格予測モデルの学習に失敗しました: {exc}")
    else:
        render_compact_metrics(
            st.columns(3),
            [
                ("評価 MAE", format_jpy(price_model.metrics["mae_jpy"])),
                ("評価 R²", f"{price_model.metrics['r2']:.3f}"),
                ("学習サンプル数", f"{int(price_model.metrics['sample_count']):,}"),
            ],
        )

        mount_options = sorted(
            option
            for option in catalog_df["mount_type"].dropna().astype(str).unique().tolist()
            if option
        )
        if not mount_options:
            mount_options = ["unknown"]
        default_mount = str(price_model.defaults.get("mount_type") or mount_options[0])
        default_mount_index = mount_options.index(default_mount) if default_mount in mount_options else 0

        price_left, price_right = st.columns([1.15, 1.25], gap="large")
        with price_left:
            with st.form("price_prediction_form"):
                input_col1, input_col2, input_col3 = st.columns(3)
                capacitance_input = input_col1.number_input(
                    "容量 (uF)",
                    min_value=0.1,
                    value=float(price_model.defaults.get("capacitance_uF", 100.0)),
                )
                voltage_input = input_col1.number_input(
                    "耐圧 (V)",
                    min_value=0.1,
                    value=float(price_model.defaults.get("voltage_V", 35.0)),
                )
                tolerance_input = input_col2.number_input(
                    "許容差 (%)",
                    min_value=0.0,
                    value=float(price_model.defaults.get("tolerance_percent", 20.0)),
                )
                diameter_input = input_col2.number_input(
                    "直径 (mm)",
                    min_value=0.0,
                    value=float(price_model.defaults.get("diameter_mm", 10.0)),
                )
                height_input = input_col3.number_input(
                    "高さ (mm)",
                    min_value=0.0,
                    value=float(price_model.defaults.get("height_mm", 10.0)),
                )
                lifetime_input = input_col3.number_input(
                    "寿命 (hours)",
                    min_value=0.0,
                    value=float(price_model.defaults.get("lifetime_hours", 2000.0)),
                )
                mount_type_input = st.selectbox(
                    "実装形態",
                    options=mount_options,
                    index=default_mount_index,
                )
                submitted = st.form_submit_button("価格を予測", use_container_width=True)

        with price_right:
            if submitted:
                predicted_price = predict_price(
                    price_model,
                    {
                        "capacitance_uF": capacitance_input,
                        "voltage_V": voltage_input,
                        "tolerance_percent": tolerance_input,
                        "diameter_mm": diameter_input,
                        "height_mm": height_input,
                        "lifetime_hours": lifetime_input,
                        "mount_type": mount_type_input,
                    },
                )
                render_compact_metrics(
                    st.columns(2),
                    [
                        ("予測単価", format_jpy(predicted_price)),
                        ("実装形態", mount_type_input),
                    ],
                )

                comparison_pool = catalog_df.dropna(
                    subset=["capacitance_uF", "voltage_V", "price_jpy"]
                ).copy()
                comparison_pool["spec_gap"] = (
                    (comparison_pool["capacitance_uF"] - capacitance_input).abs()
                    + (comparison_pool["voltage_V"] - voltage_input).abs()
                )
                similar_parts = comparison_pool.sort_values("spec_gap").head(5)
                st.dataframe(
                    similar_parts[
                        [
                            "part_number",
                            "manufacturer",
                            "source",
                            "mount_type",
                            "capacitance_uF",
                            "voltage_V",
                            "price_jpy",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                    height=250,
                    column_config={
                        "part_number": "品番",
                        "manufacturer": "メーカー",
                        "source": "ソース",
                        "mount_type": "実装形態",
                        "capacitance_uF": st.column_config.NumberColumn(
                            "容量 (uF)", format="%.4g"
                        ),
                        "voltage_V": st.column_config.NumberColumn(
                            "耐圧 (V)", format="%.4g"
                        ),
                        "price_jpy": st.column_config.NumberColumn(
                            "単価 (JPY)", format="%.2f"
                        ),
                    },
                )
            else:
                st.info("左のスペックを入力して価格を予測してください。")
