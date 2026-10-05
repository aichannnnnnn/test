# devin-usage

Devinの利用量（ACU）を、5時間などの区間ごとに集計して表示するツールです。
Python 3.10以上の標準ライブラリだけで動きます。

## 準備

1. https://app.devin.ai/settings/personal-access-tokens でPersonal Access Token（`cog_...`）を作る
2. 組織ID（`org-...`）を確認する
3. 環境変数に設定する

```bash
export DEVIN_PAT="cog_..."
export DEVIN_ORG_ID="org-..."
```

## 使い方

```bash
# ターミナルに表で表示（5時間 x 3区間）
python3 -m devin_usage report
python3 -m devin_usage report 6 4   # 4時間 x 6区間

# Webダッシュボードを起動して http://127.0.0.1:8765/ を開く
python3 -m devin_usage serve

# スマホなどから Tailscale 経由で見る場合
python3 -m devin_usage serve --host 0.0.0.0

# APIを使わずダミーデータで試す
python3 -m devin_usage --demo serve
```

`pip install -e .` でインストールすると、`devin-usage serve` のように短く呼び出せます。

## 注意

- セッションのACUは、開始した時刻の区間にまとめて数えます。
- APIの呼び出しは60秒間キャッシュします。
- `--host 0.0.0.0` で公開すると、同じネットワークの人も利用量を見られます。信頼できるネットワークでだけ使ってください。

## テスト

```bash
pip install -e '.[dev]'
pytest
```
