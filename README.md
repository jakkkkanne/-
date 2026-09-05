# Threads 運用自動化 (threads_ops)

Threads (Meta) の運用フローを自動化するパイプラインです。

```
リサーチ(競合分析) → 下書き生成 → 人による承認(CLI) → 投稿
```

投稿は必ず人が CLI 上で承認したものだけが対象になります。承認前に自動投稿されることはありません。

## セットアップ

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 必要に応じて編集
```

## 使い方

### 1. リサーチ(競合アカウント分析)

Meta の公式 Threads API には他アカウントの投稿を取得するエンドポイントが存在しません
(自アカウントの投稿・返信・インサイトの管理用 API のみ提供)。そのため、このツールの
競合分析は **自分で用意したデータ** を読み込む方式にしています。`data/competitors/` に
アカウントごとの JSON ファイルを置いてください(サンプル: `data/competitors/example_account.json`)。
自動スクレイピングは Threads の利用規約に抵触するリスクがあるため実装していません。

各ファイルの形式:

```json
{
  "posts": [
    {
      "account": "some_account",
      "text": "投稿本文",
      "posted_at": "2026-07-20T09:00:00+00:00",
      "likes": 100,
      "replies": 10,
      "reposts": 5,
      "hashtags": ["タグ1"]
    }
  ]
}
```

実行:

```bash
python -m threads_ops research
```

キーワード・ハッシュタグの頻出度、反応が良い時間帯、平均文字数などを集計し
`data/reports/` にレポート(JSON)として保存します。

### 2. 下書き生成

```bash
python -m threads_ops draft --topic "朝活" --count 3
```

最新のリサーチレポートをもとに下書きを生成し、`data/drafts/pending/` に保存します。
`ANTHROPIC_API_KEY` が設定されていれば Claude API で自然な文章を生成し、未設定なら
オフラインのテンプレート生成にフォールバックします。

### 3. 承認(CLI)

```bash
python -m threads_ops review
```

下書きを1件ずつ表示し、`a`(承認) / `r`(却下) / `e`(編集して再確認) / `s`(保留) / `q`(終了)
で判断します。承認したものは `data/drafts/approved/` に移動します。

### 4. 投稿

```bash
python -m threads_ops publish
```

`data/drafts/approved/` にある下書きのみを対象に投稿します。既定 (`THREADS_OPS_PUBLISHER=mock`)
ではネットワーク呼び出しを一切行わず、投稿内容と結果を `data/drafts/history.jsonl` に記録するだけです。
実際に投稿するには `.env` で `THREADS_OPS_PUBLISHER=real` にし、`THREADS_ACCESS_TOKEN` /
`THREADS_USER_ID` を設定してください(Meta の [Threads API](https://developers.facebook.com/docs/threads)
のセットアップが別途必要です)。

### まとめて実行

```bash
python -m threads_ops run-all --topic "朝活" --count 3
```

research → draft → review(対話) → publish を順番に実行します。

## テスト

```bash
pytest -q
```

## ディレクトリ構成

```
threads_ops/       パイプライン本体
  config.py         環境変数ベースの設定
  models.py         CompetitorPost / ResearchReport / Draft
  research.py        競合データ分析
  draft.py            下書き生成 (テンプレート / Anthropic)
  approval.py       CLI 承認フロー
  publish.py         投稿 (Mock / 実 API)
  cli.py            コマンド群
data/
  competitors/      競合データ(自分で用意)
  reports/          生成されたリサーチレポート
  drafts/
    pending/        承認待ち
    approved/       承認済み(投稿対象)
    rejected/       却下済み
    posted/         投稿済み
    history.jsonl   投稿履歴ログ
```

## 制限事項

- 競合他社の投稿を自動収集する機能はありません(API 未提供・利用規約リスクのため)。
  必要なデータは手動で `data/competitors/` に投入してください。
- 既定の投稿処理はモックです。実際に Threads へ投稿するには Meta 側のアプリ登録・
  アクセストークン発行が必要です。

---

# MT5 ドル円自動売買 (mt5_trading)

MetaTrader 5 (MT5) 上で USD/JPY を自動売買する Python ボットです。
**MetaTrader5 パッケージは Windows(または Wine)上で稼働中の MT5 ターミナル
がないと動作しません。** そのため戦略ロジック(`indicators.py` /
`strategy.py` / `risk.py`)は MT5 に依存しない純粋な関数として分離してあり、
このリポジトリのテスト環境(Linux)でも `pytest` で検証できます。実際の
発注部分 (`mt5_client.py` / `trader.py`) はご自身の Windows 環境 + MT5
ターミナル + ブローカー口座で実行してください。

## 戦略

EMA クロス + RSI フィルターのトレンドフォロー戦略です。

- 短期 EMA が長期 EMA を **上に** クロス(ゴールデンクロス)かつ RSI が
  買われすぎ水準以下 → **買い**
- 短期 EMA が長期 EMA を **下に** クロス(デッドクロス)かつ RSI が
  売られすぎ水準以上 → **売り**
- 損切り/利確は ATR(平均真の値幅)の倍数で設定
- ロットサイズは口座残高に対するリスク許容%から自動計算(固定ロットも可)

## セーフティ機構(既定で有効)

- **ドライラン既定**: `MT5_ENABLE_LIVE_TRADING=true` を明示的に設定しない限り、
  実際の発注は一切行わず、ログに「何を発注するか」だけを出力します。
- スプレッドが `MT5_MAX_SPREAD_POINTS` を超える時間帯はエントリーを見送り
- 1日の含み損が `MT5_MAX_DAILY_LOSS_PERCENT` に達したら当日は新規エントリー停止
- マジックナンバーで自分が建てたポジションのみ管理(他の EA/手動注文に干渉しない)

## セットアップ

```bash
pip install -r requirements.txt   # pandas は共通。MetaTrader5 は Windows のみ
cp .env.example .env              # MT5_LOGIN / MT5_PASSWORD / MT5_SERVER 等を編集
```

Windows 側で MT5 ターミナルを起動し、対象口座にログインした状態にしてください
(ブローカーによっては自動売買を有効化する設定も必要です)。

## 使い方

```bash
# 設定内容を確認(接続不要)
python -m mt5_trading check-config

# 1サイクルだけ実行(MT5 ターミナルへの接続が必要)
python -m mt5_trading run --once

# ループ実行(Ctrl+C で停止)。既定はドライランなので実発注はされません
python -m mt5_trading run
```

実際に発注させるには `.env` で `MT5_ENABLE_LIVE_TRADING=true` にしてください。
**必ずデモ口座で十分に検証してから**、少額のリアル口座で運用することを
強く推奨します。過去の値動きへの最適化が将来の利益を保証するものではなく、
自動売買には資金を失うリスクが伴います。

## テスト

```bash
pytest tests/test_mt5_indicators.py tests/test_mt5_strategy.py tests/test_mt5_risk.py -q
```

## ディレクトリ構成

```
mt5_trading/
  config.py         環境変数ベースの設定(発注安全フラグ含む)
  indicators.py     EMA / RSI / ATR(MT5非依存、純粋関数)
  strategy.py       EMAクロス+RSIフィルターのシグナル生成(MT5非依存)
  risk.py           ロットサイズ計算・SL/TP計算(MT5非依存)
  mt5_client.py     MetaTrader5 パッケージのラッパー(Windows/Wine専用)
  trader.py         売買ループ本体(接続・シグナル判定・発注・リスク管理)
  cli.py            コマンド群
```
