# AI部品クロスリファレンス・価格最適化 PoC

Mouser の部品データをベースに、アルミ電解コンデンサの代替部品検索、コスト削減額の可視化、市場マップ、簡易価格予測を行う Streamlit アプリです。  
`digi.xlsx` が同じフォルダか 1 つ上のフォルダにあれば、Digi-Key データも自動で読み込みます。

## 実装済み機能

- `最優先` 代替部品検索
  同容量・必要耐圧以上・在庫ありを hard filter とし、価格差・仕様距離・在庫をまとめた `match_score` で候補を順位付けします。
- `最優先` コスト削減額の表示
  単価差額、削減率、生産数量あたりのロット削減額を表示します。
- `中` 市場マップ
  容量、耐圧、寸法、寿命、価格を使って PCA + K-means で 2 次元マップ化します。
- `低` 価格予測
  RandomForestRegressor による簡易単価予測を搭載しています。
- `低` ホワイトスペース探索
  明示機能としては未実装です。市場マップとクラスタ差分を使って発表で構想説明できる状態です。

## セットアップ

```bash
pip install -r requirements.txt
python clean_csv.py
streamlit run app.py
```

起動後はブラウザで `http://localhost:8501` を開きます。

## CLI で代替候補を確認する

```bash
python search_alternatives.py --part-number MAL214699805E3 --production-qty 10000 --include-optional
```

引数を省略した場合は対話入力になります。

## 画面構成

- `代替部品検索`
  品番と生産数量を入力し、代替候補ランキングと削減額グラフを表示します。
- `市場マップ`
  PCA で圧縮した市場分布をクラスタ別に表示します。
- `価格予測（簡易版）`
  スペックを入力すると参考単価を予測します。

## 主要ファイル

- `app.py`
  Streamlit UI 本体
- `search_alternatives.py`
  代替候補検索ロジックと CLI
- `analysis_models.py`
  市場マップと価格予測モデル
- `catalog.py`
  Mouser/Digi-Key データの正規化処理
- `clean_csv.py`
  Mouser CSV の前処理

## 前処理で使う主な列

`clean_csv.py` では次の列を作成または補完します。

- `capacitance_uF`
- `voltage_V`
- `tolerance_percent`
- `price_jpy`
- `stock`
- `diameter_mm`
- `height_mm`
- `lifetime_hours`
- `mount_type`
- `is_aluminum_electrolytic`

## 注意点

- 通常利用では Mouser API を呼びません。ローカルの CSV / XLSX を読みます。
- `digi.xlsx` がない場合でもアプリは Mouser データだけで動きます。
- 価格予測は PoC 用の簡易モデルです。実調達価格の保証には使わない前提です。
