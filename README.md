# Threads 運用会社 (threads_ops)

Threads (Meta) の運用を、複数SNS展開(X・Threads・Instagram・note)を見据えた
「運用会社」の第一弾として自動化するパイプラインです。会社は4部門で構成されます。

| 部門 | 役割 | 対応モジュール |
| --- | --- | --- |
| リサーチ部門 | 競合投稿を分析しレポート化 | `research.py` |
| マーケティング部門 | レポートから投稿トーン・頻度・ハッシュタグ戦略を立案 | `marketing.py` |
| 戦略部門 | コンテンツの柱・優先トピック・KPI目標を決定 | `strategy.py` |
| 秘書部門 | 上記3部門を統括し、下書き生成まで一括実行してレポートを作成 | `secretary.py` |

```
リサーチ(競合分析) → マーケティング(戦術立案) → 戦略(トピック決定)
  → 下書き生成 → 人による承認(CLI) → 投稿
```

投稿は必ず人が CLI 上で承認したものだけが対象になります。承認前に自動投稿されることはありません
(秘書部門も含め、どの部門も承認・投稿は代行しません)。

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

## 会社の部門コマンド

### マーケティング部門

```bash
python -m threads_ops marketing
```

最新のリサーチレポートから、投稿トーン・週あたりの投稿頻度・推奨ハッシュタグ・
成長施策(growth tactics)をまとめた `MarketingPlan` を生成し `data/marketing/` に保存します。

### 戦略部門

```bash
python -m threads_ops strategy
```

最新のレポート + マーケティングプランから、コンテンツの柱・優先トピック・
週次投稿目標・KPI目標(エンゲージメント/フォロワー成長率の目安)をまとめた
`StrategyPlan` を生成し `data/strategy/` に保存します。優先トピックは上位ハッシュタグ
(なければキーワード)から選ばれます。

### 秘書部門(会社を一括運用)

```bash
python -m threads_ops secretary --topics 3 --count 2
```

リサーチ → マーケティング → 戦略 の3部門を順に実行し、戦略部門が決めた優先トピック
(既定で上位3件)ごとに下書きを生成します。実行結果は各部門のサマリーと
次にやるべきアクション(`review` → `publish`)をまとめた `CompanyReport` として
`data/secretary/` に保存されます。秘書部門は下書きを作るところまでで止まり、
承認・投稿は必ず人が `review` / `publish` を実行します。

## テスト

```bash
pytest -q
```

## ディレクトリ構成

```
threads_ops/       パイプライン本体
  config.py         環境変数ベースの設定
  models.py         CompetitorPost / ResearchReport / MarketingPlan / StrategyPlan / CompanyReport / Draft
  research.py        [リサーチ部門] 競合データ分析
  marketing.py        [マーケティング部門] トーン・頻度・ハッシュタグ戦略の立案
  strategy.py          [戦略部門] コンテンツの柱・優先トピック・KPI目標の決定
  secretary.py          [秘書部門] 各部門を統括して一括実行し会社レポートを作成
  draft.py            下書き生成 (テンプレート / Anthropic)
  approval.py       CLI 承認フロー
  publish.py         投稿 (Mock / 実 API)
  cli.py            コマンド群
data/
  competitors/      競合データ(自分で用意)
  reports/          生成されたリサーチレポート
  marketing/        マーケティングプラン
  strategy/         戦略プラン
  secretary/        秘書部門の会社運用レポート
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
