# AI価格最適化・代替部品検索 PoC

アルミ電解コンデンサを対象に、`元部品の品番` から代替候補とコスト削減額を出す PoC です。  
最終的なデモ範囲は次の 2 本に絞っています。

- `代替部品検索`
- `価格予測（簡易版）`

市場マップは途中で試作しましたが、現データでは説明コストの割に価値が弱かったため、最終 UI からは外しています。

## この PoC でできること

- 元部品と近い代替候補を検索する
- 単価差額、削減率、ロット削減額を表示する
- 容量、耐圧、許容差、寸法の差分を個別項目で確認する
- 仕様値から参考単価を推定する

## 実装済み機能

### 1. 前処理

`clean_csv.py` が Mouser CSV を読み込み、説明文から次の項目を抽出します。

- `capacitance_uF`
- `voltage_V`
- `tolerance_percent`
- `diameter_mm`
- `height_mm`
- `lifetime_hours`
- `price_jpy`
- `stock`
- `mount_type`

そのうえで、アルミ電解コンデンサだけを `capacitors_clean.csv` に保存します。

### 2. データ統合

`catalog.py` が Mouser の `capacitors_clean.csv` を基本データとして読み込みます。  
同じ階層、または 1 つ上の階層に `digi.xlsx` があれば、自動で Digi-Key データも結合します。

### 3. 代替部品検索

`search_alternatives.py` が代替候補を検索します。

検索の基本条件は次です。

- 容量が元部品の ±2% 以内
- 耐圧が元部品以上
- 在庫が 0 より大きい
- 元部品自身は除外
- 許容差が分かる場合、候補は元部品より悪化しない
- 寸法が分かる場合、候補の直径と高さは元部品の 115% 以下
- 寿命が分かる場合、候補は元部品以上

まず `mount_type` が同じ候補だけで探し、見つからない場合だけ `mount_type` 制約を外して再検索します。

内部では総合順位付けのために `match_score` を計算していますが、UI 上は総合点を見せず、個別項目で判断する構成にしています。

画面で表示する比較項目は次です。

- `容量誤差 (%)`
- `耐圧余裕 (V)`
- `許容差余裕 (%)`
- `直径余裕 (mm)`
- `高さ余裕 (mm)`

### 4. コスト削減額の表示

代替候補ごとに次を計算します。

- `unit_saving_jpy = original_price - candidate_price`
- `saving_rate_percent = unit_saving_jpy / original_price * 100`
- `saving_for_lot_jpy = unit_saving_jpy * production_qty`

UI では、おすすめ候補の単価差額とロット削減額を先頭に表示します。

### 5. 価格予測（簡易版）

`analysis_models.py` が `RandomForestRegressor` で参考単価を推定します。

入力特徴量は次です。

- `capacitance_uF`
- `voltage_V`
- `tolerance_percent`
- `diameter_mm`
- `height_mm`
- `lifetime_hours`
- `mount_type`

目的変数は `price_jpy` です。  
欠損値は中央値または最頻値で補完し、`mount_type` は one-hot 化して学習します。

現在のローカルデータでの参考評価値は次です。

- hold-out: `MAE = 555円`, `R² = 0.760`
- 5 分割 CV 平均: `MAE = 463円`, `R² = 0.769`

これは「相場の目安」には使えますが、実調達価格の保証には使わない前提です。

## 実行方法

```bash
pip install -r requirements.txt
python clean_csv.py
streamlit run app.py
```

起動後は `http://localhost:8501` を開いてください。

## CLI 実行例

```bash
python search_alternatives.py --part-number MAL214699805E3 --production-qty 10000 --include-optional
```

## 主要ファイル

- `app.py`
  Streamlit UI。本番デモ用の入口です。
- `search_alternatives.py`
  代替候補検索と CLI。
- `analysis_models.py`
  価格予測モデル。
- `catalog.py`
  Mouser / Digi-Key の共通スキーマ化とパーサ群。
- `clean_csv.py`
  Mouser CSV の前処理。
- `fetch_mouser.py`
  Mouser データ取得用スクリプト。

## 現在の UI 構成

- `代替部品検索`
- `価格予測（簡易版）`

## PoC としての評価

今回の要件が

- 最優先: `代替部品検索`
- 最優先: `コスト削減額の表示`
- 低: `価格予測は簡易版で可`

であれば、このリポジトリは PoC 完成扱いで問題ありません。

ただし、次は明確に残っています。

- 完全互換判定ではなく、近い候補探索である
- 価格予測は参考値であり、実見積の代替ではない
- 市場マップとホワイトスペース探索は最終 UI から外している

## 提出向け補助

`.py` のテキスト版として、同じ内容の `.txt` ファイルも併せて置いています。
