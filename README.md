# AI部品クロスリファレンス・価格最適化 PoC

このプロジェクトは、Mouserの部品データを使って、コンデンサの品番検索・代替候補検索・価格比較・コスト削減シミュレーションを行う授業用PoCです。

## ファイル構成

- `fetch_mouser.py`  
  （任意）Mouser Search APIからデータを取得し、`capacitors.csv` を作成します。`category` 列も保存します。
- `clean_csv.py`  
  `capacitors.csv` を整形し、アルミ電解コンデンサのみを残した `capacitors_clean.csv` を作成します。
- `search_alternatives.py`  
  CLIで代替候補検索と削減額の試算を行います。
- `app.py`  
  StreamlitのUIで代替候補検索・ランキング表示・削減額表示を行います。

## 入力CSV形式

`capacitors.csv` には以下の列が必要です。

- `part_number`
- `manufacturer`
- `description`
- `availability`
- `price`
- `datasheet_url`
- `product_url`

任意（推奨）:

- `category`（`clean_csv.py` でより高精度にフィルタするために利用）

## セットアップ

```bash
pip install -r requirements.txt
```

## 実行方法

1. CSVを整形する

```bash
python clean_csv.py
```

`capacitors_clean.csv` に以下の列が追加されます。

- `capacitance_uF`
- `voltage_V`
- `tolerance_percent`
- `price_jpy`
- `stock`
- `is_aluminum_electrolytic`

アルミ電解コンデンサ判定ルール:

- 優先1: `category` が「アルミ系 + 電解系」に一致
- 優先2: `description` が「アルミ系 + 電解系」に一致（フォールバック）

2. CLIで代替候補検索を実行する

```bash
python search_alternatives.py
```

品番入力後、以下を表示します。

- 元部品の仕様
- 代替候補ランキング（安い順）
- 単価差額
- 削減率
- 生産数10,000個時の削減額

3. Streamlitアプリを起動する

```bash
streamlit run app.py
```

アプリでは以下を表示します。

- 品番入力欄
- 生産数入力欄
- 元部品の仕様
- 代替候補ランキング
- コスト削減額
- `product_url` リンク

## （任意）Mouser APIから最新データ取得

APIキーはコードに直書きせず、環境変数で設定してください。

```bash
export MOUSER_API_KEY="your_key_here"
python fetch_mouser.py
```

これで `capacitors.csv` が更新されます。

## 補足

- メイン処理（`clean_csv.py` / `search_alternatives.py` / `app.py`）はローカルCSV処理です。
- アプリはMouser APIを毎回呼び出しません。
- ファイル欠落・列不足・品番未一致などの基本的なエラー処理を実装しています。
- 環境によって `python` が使えない場合は `python3` を使用してください。
