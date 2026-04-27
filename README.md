# AI部品クロスリファレンス・価格最適化 PoC

Mouserの部品データを使って、アルミ電解コンデンサの代替候補検索とコスト削減シミュレーションを行うアプリです。

## 最短で起動する手順

プロジェクト直下で、次の順に実行してください。

```bash
pip install -r requirements.txt
python clean_csv.py
streamlit run app.py
```

ブラウザで `http://localhost:8501` を開くとアプリが表示されます。  
CLI版を使う場合は次を実行します。

```bash
python search_alternatives.py
```

`python` が使えない環境では `python3` / `pip3` に読み替えてください。

## このプロジェクトで使うファイル

- `fetch_mouser.py`  
  （任意）Mouser Search APIから部品データを取得して `capacitors.csv` を作成します。
- `clean_csv.py`  
  `capacitors.csv` を整形し、アルミ電解コンデンサのみを残して `capacitors_clean.csv` を作成します。
- `search_alternatives.py`  
  ターミナルで品番入力して代替候補を表示するCLIツールです。
- `app.py`  
  StreamlitのWebアプリです。品番・生産数を入力してランキングと削減額を表示します。

## clean_csv.py で追加される列

- `capacitance_uF`
- `voltage_V`
- `tolerance_percent`
- `price_jpy`
- `stock`
- `is_aluminum_electrolytic`

アルミ電解判定は次の順で行います。

- `category` の文字列を優先判定
- `description` の文字列をフォールバック判定

## 入力CSV（capacitors.csv）の必要列

- `part_number`
- `manufacturer`
- `description`
- `availability`
- `price`
- `datasheet_url`
- `product_url`

任意（推奨）:

- `category`（フィルタ精度向上のため）

## Mouser APIからデータを再取得する（任意）

APIキーを環境変数に設定して実行します。

```bash
export MOUSER_API_KEY="your_key_here"
python fetch_mouser.py
```

取得条件を変更したい場合:

```bash
export MOUSER_KEYWORD="aluminum electrolytic capacitor"
export MOUSER_MAX_RECORDS="300"
export MOUSER_PAGE_SIZE="50"
python fetch_mouser.py
```

## 注意点

- `app.py` は `python app.py` ではなく、必ず `streamlit run app.py` で起動してください。
- `clean_csv.py` / `search_alternatives.py` / `app.py` はローカルCSVを使うため、通常利用時にMouser APIを繰り返し呼びません。
