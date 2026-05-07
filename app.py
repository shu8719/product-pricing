from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis_models import build_market_map_frame, predict_price, train_price_model
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


@st.cache_data
def get_catalog() -> pd.DataFrame:
    return load_clean_data(include_optional=True)


@st.cache_data
def get_market_map_data() -> pd.DataFrame:
    return build_market_map_frame(get_catalog())


@st.cache_resource
def get_price_model():
    return train_price_model(get_catalog())


st.set_page_config(
    page_title="AI部品クロスリファレンス・価格最適化",
    page_icon=":electric_plug:",
    layout="wide",
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

search_tab, market_tab, price_tab = st.tabs(
    ["代替部品検索", "市場マップ", "価格予測（簡易版）"]
)

with search_tab:
    control_left, control_right, control_right2 = st.columns([2, 1, 1])
    with control_left:
        part_number = st.text_input(
            "元部品の品番",
            placeholder="例: MAL214699805E3",
        ).strip()
    with control_right:
        production_qty = st.number_input(
            "生産数量",
            min_value=1,
            value=DEFAULT_PRODUCTION_QTY,
            step=100,
        )
    with control_right2:
        top_n = st.slider("表示件数", min_value=5, max_value=20, value=10)

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
            original_col1, original_col2, original_col3, original_col4, original_col5 = st.columns(5)
            original_col1.metric("容量", f"{format_float(original['capacitance_uF'])} uF")
            original_col2.metric("耐圧", f"{format_float(original['voltage_V'])} V")
            original_col3.metric(
                "在庫数",
                f"{int(original['stock']):,}" if pd.notna(original["stock"]) else "-",
            )
            original_col4.metric("単価", format_jpy(original["price_jpy"]))
            original_col5.metric("ソース", str(original.get("source") or "-"))

            original_info = pd.DataFrame(
                [
                    {"項目": "品番", "値": original["part_number"]},
                    {"項目": "メーカー", "値": original["manufacturer"]},
                    {"項目": "実装形態", "値": original.get("mount_type") or "-"},
                    {"項目": "説明", "値": original["description"]},
                    {"項目": "商品URL", "値": original["product_url"]},
                ]
            )
            st.dataframe(original_info, hide_index=True, use_container_width=True)

            if alternatives.empty:
                st.warning("指定した条件に一致する代替候補は見つかりませんでした。")
            else:
                cheaper = alternatives[alternatives["is_cost_down"]].copy()
                ranking = cheaper if show_cost_down_only and not cheaper.empty else alternatives
                ranking = ranking.head(top_n).copy()

                if cheaper.empty:
                    st.warning(
                        "互換候補は見つかりましたが、現在のデータではコストダウン候補はありません。"
                    )

                best = ranking.iloc[0]
                metrics = st.columns(4)
                metrics[0].metric("推奨候補", str(best["part_number"]))
                metrics[1].metric("単価差額", format_jpy(best["unit_saving_jpy"]))
                metrics[2].metric(
                    f"{int(production_qty):,} 個時の削減額",
                    format_jpy(best["saving_for_lot_jpy"]),
                )
                metrics[3].metric("互換性スコア", f"{float(best['match_score']):.2f}")
                st.caption(
                    "検索モード: "
                    + (
                        "同一実装形態を維持した strict search"
                        if str(best["compatibility_tier"]) == "strict"
                        else "候補不足のため実装形態制約を緩めた relaxed search"
                    )
                )

                ranking_columns = [
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
                    "product_url",
                ]
                st.dataframe(
                    ranking[ranking_columns],
                    hide_index=True,
                    use_container_width=True,
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
                        "stock": st.column_config.NumberColumn("在庫数", format="%d"),
                        "price_jpy": st.column_config.NumberColumn(
                            "単価 (JPY)", format="%.2f"
                        ),
                        "unit_saving_jpy": st.column_config.NumberColumn(
                            "単価差額 (JPY)", format="%.2f"
                        ),
                        "saving_rate_percent": st.column_config.NumberColumn(
                            "削減率 (%)", format="%.2f"
                        ),
                        "saving_for_lot_jpy": st.column_config.NumberColumn(
                            "ロット削減額 (JPY)",
                            format="%.2f",
                        ),
                        "match_score": st.column_config.NumberColumn(
                            "互換性スコア", format="%.2f"
                        ),
                        "product_url": st.column_config.LinkColumn(
                            "商品URL",
                            display_text="開く",
                        ),
                    },
                )

                chart_df = ranking.copy()
                chart_df["label"] = chart_df["part_number"].astype(str)
                saving_chart = px.bar(
                    chart_df,
                    x="label",
                    y="saving_for_lot_jpy",
                    color="source",
                    title="候補ごとのロット削減額",
                    labels={
                        "label": "代替候補",
                        "saving_for_lot_jpy": "削減額 (JPY)",
                        "source": "データソース",
                    },
                )
                saving_chart.update_layout(xaxis_tickangle=-30, height=420)
                st.plotly_chart(saving_chart, use_container_width=True)

with market_tab:
    st.caption("容量・耐圧・寸法・寿命・価格をもとに PCA で 2 次元化した市場マップです。")
    try:
        market_df = get_market_map_data()
    except Exception as exc:
        st.error(f"市場マップの作成に失敗しました: {exc}")
    else:
        available_sources = sorted(market_df["source"].dropna().unique().tolist())
        selected_sources = st.multiselect(
            "表示ソース",
            options=available_sources,
            default=available_sources,
        )
        filtered_market_df = market_df[market_df["source"].isin(selected_sources)].copy()

        market_chart = px.scatter(
            filtered_market_df,
            x="pc1",
            y="pc2",
            color="cluster",
            symbol="source",
            hover_name="part_number",
            hover_data={
                "manufacturer": True,
                "capacitance_uF": ":.4g",
                "voltage_V": ":.4g",
                "price_jpy": ":.2f",
                "stock": True,
                "pc1": False,
                "pc2": False,
            },
            title="アルミ電解コンデンサ 市場マップ",
        )
        market_chart.update_traces(marker=dict(size=11, opacity=0.8))
        market_chart.update_layout(height=620)
        st.plotly_chart(market_chart, use_container_width=True)

        cluster_summary = (
            filtered_market_df.groupby("cluster")
            .agg(
                部品数=("part_number", "count"),
                平均単価=("price_jpy", "mean"),
                平均耐圧=("voltage_V", "mean"),
            )
            .round(2)
            .reset_index()
        )
        st.dataframe(cluster_summary, hide_index=True, use_container_width=True)

with price_tab:
    st.caption("現行データから単価を回帰する簡易モデルです。発表では参考値として扱う想定です。")
    try:
        price_model = get_price_model()
    except Exception as exc:
        st.error(f"価格予測モデルの学習に失敗しました: {exc}")
    else:
        metric_cols = st.columns(3)
        metric_cols[0].metric("評価 MAE", format_jpy(price_model.metrics["mae_jpy"]))
        metric_cols[1].metric("評価 R²", f"{price_model.metrics['r2']:.3f}")
        metric_cols[2].metric("学習サンプル数", f"{int(price_model.metrics['sample_count']):,}")

        mount_options = sorted(
            option
            for option in catalog_df["mount_type"].dropna().astype(str).unique().tolist()
            if option
        )
        if not mount_options:
            mount_options = ["unknown"]
        default_mount = str(price_model.defaults.get("mount_type") or mount_options[0])
        default_mount_index = mount_options.index(default_mount) if default_mount in mount_options else 0

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
            submitted = st.form_submit_button("価格を予測")

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
            st.metric("予測単価", format_jpy(predicted_price))

            comparison_pool = catalog_df.dropna(
                subset=["capacitance_uF", "voltage_V", "price_jpy"]
            ).copy()
            comparison_pool["spec_gap"] = (
                (comparison_pool["capacitance_uF"] - capacitance_input).abs()
                + (comparison_pool["voltage_V"] - voltage_input).abs()
            )
            similar_parts = comparison_pool.sort_values("spec_gap").head(5)
            st.caption("参考: 近いスペックの既存部品")
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
                column_config={
                    "part_number": "品番",
                    "manufacturer": "メーカー",
                    "source": "ソース",
                    "mount_type": "実装形態",
                    "capacitance_uF": st.column_config.NumberColumn(
                        "容量 (uF)", format="%.4g"
                    ),
                    "voltage_V": st.column_config.NumberColumn("耐圧 (V)", format="%.4g"),
                    "price_jpy": st.column_config.NumberColumn("単価 (JPY)", format="%.2f"),
                },
            )
