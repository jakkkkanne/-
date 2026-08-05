# Threads 運用会社 (threads_ops)

Threads (Meta) の運用を、複数SNS展開(X・Threads・Instagram・note)を見据えた
「運用会社」の第一弾として自動化するパイプラインです。会社は5部門で構成されます。

**現在の運用方針:** ジャンルは子育て(あるある・困りごと・解決法)に特化し、
閲覧数1万以上の競合投稿の「型」を分析して再現しつつ、「解決法」投稿に楽天
アフィリエイトの商品リンクを添えて収益化します。投稿頻度は週42件(1日6投稿)を
公式カデンスとして運用します(`.env` の `THREADS_OPS_WEEKLY_POST_TARGET`)。

| 部門 | 役割 | 対応モジュール |
| --- | --- | --- |
| リサーチ部門 | 競合投稿を分析しレポート化。閲覧数1万以上の投稿を「バイラル投稿」として型(あるある/困りごと/解決法)ごとに分析 | `research.py` |
| マーケティング部門 | レポートから投稿トーン・頻度・ハッシュタグ戦略を立案 | `marketing.py` |
| 戦略部門 | コンテンツの柱・優先トピック・KPI目標を決定 | `strategy.py` |
| 収益管理部門 | KPI目標と投稿実績から週次の見込み利益(エンゲージメント・フォロワー・楽天アフィリエイト)を試算 | `finance.py` / `affiliate.py` |
| 秘書部門 | 上記4部門を統括し、下書き生成まで一括実行してレポートを作成(定期自動実行も可) | `secretary.py` |

```
リサーチ(競合分析) → マーケティング(戦術立案) → 戦略(トピック決定) → 収益管理(利益試算)
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
アカウントごとの JSON ファイルを置いてください(現在の運用ジャンルのサンプル:
`data/competitors/childcare_viral_accounts.json`。ジャンル非依存の汎用フォーマット例は
`data/samples/format_example.json` に移動してあります — こちらは `data/competitors/`
配下ではないので `research` の集計対象には含まれません)。
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
      "views": 12000,
      "hashtags": ["タグ1"],
      "post_type": "解決法"
    }
  ]
}
```

`views`(閲覧数)と `post_type`(`あるある` / `困りごと` / `解決法` など、手動でタグ付け)
は任意項目です。`views` が `.env` の `THREADS_OPS_MIN_VIRAL_VIEWS`(既定 10,000)以上の
投稿は「バイラル投稿」として別集計され、`post_type` ごとに平均閲覧数・平均文字数・
冒頭パターンをまとめた `patterns_by_type` がレポートに含まれます。これが
「型を分析して再現する」の元データです。

実行:

```bash
python -m threads_ops research
```

キーワード・ハッシュタグの頻出度、反応が良い時間帯、平均文字数、バイラル投稿の型などを
集計し `data/reports/` にレポート(JSON)として保存します。

### 2. 下書き生成

```bash
python -m threads_ops draft --topic "朝活" --count 3
```

最新のリサーチレポートをもとに下書きを生成し、`data/drafts/pending/` に保存します。
`ANTHROPIC_API_KEY` が設定されていれば Claude API で自然な文章を生成し、未設定なら
オフラインのテンプレート生成にフォールバックします。マーケティングプランが保存済みなら
自動的に読み込み、トーン(カジュアル/丁寧)・成長施策を文面に反映します。
投稿本文にハッシュタグは付与しません。

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

### 収益管理部門

```bash
python -m threads_ops finance
```

最新の戦略プラン(KPI目標)と `data/drafts/history.jsonl` の投稿実績から、
週次の見込みエンゲージメント収益・フォロワー収益・**楽天アフィリエイト収益**・
下書き生成コスト・見込み利益を試算し `RevenueReport` として `data/finance/` に保存します。
単価/前提は `.env` の `THREADS_OPS_REVENUE_PER_ENGAGEMENT` / `THREADS_OPS_REVENUE_PER_FOLLOWER` /
`THREADS_OPS_FOLLOWER_COUNT` / `THREADS_OPS_COST_PER_DRAFT` /
`THREADS_OPS_WEEKLY_AFFILIATE_CLICKS` / `THREADS_OPS_RAKUTEN_CONVERSION_RATE` /
`THREADS_OPS_RAKUTEN_COMMISSION_PER_SALE` で調整してください。
**実測の収益ではなく、あくまで設定した単価・想定クリック数に基づく試算です。**

### アフィリエイト(楽天)

`affiliate.py` は、子育ての困りごと(夜泣き・離乳食・イヤイヤ期など)を
Rakuten Ichiba の検索キーワードに対応させ、リンクを生成します
(`affiliate.PRODUCT_CATALOG` にカテゴリの一覧があります)。`.env` に
`RAKUTEN_AFFILIATE_ID`([楽天アフィリエイト](https://affiliate.rakuten.co.jp/)の
審査通過後に発行されるID)を設定すると実際に収益化されるリンクを生成し、
未設定の場合は素の楽天市場検索リンク(収益化されない)にフォールバックします。
商品は具体的なブランド・型番ではなくカテゴリ単位で提案しているので、実際に紹介する
商品は投稿前に選定してください。

### 秘書部門(会社を一括運用)

```bash
python -m threads_ops secretary --topics 3 --count 2
```

リサーチ → マーケティング → 戦略 → 収益管理 の4部門を順に実行し、戦略部門が決めた
優先トピック(既定で上位3件)ごとに下書きを生成します。実行結果は各部門のサマリーと
次にやるべきアクション(`review` → `publish`)をまとめた `CompanyReport` として
`data/secretary/` に保存されます。秘書部門は下書きを作るところまでで止まり、
承認・投稿は必ず人が `review` / `publish` を実行します。

#### 定期自動実行(ループモード)

```bash
python -m threads_ops secretary --loop --interval-hours 24 --max-iterations 3
```

`--loop` を付けると、上記のサイクルを `--interval-hours` おきに繰り返します
(`--max-iterations` を省略すると Ctrl+C で止めるまで無期限に実行します)。
ループ中も下書き作成までしか行わないため、投稿には毎回人が `review` / `publish`
を実行する必要があります。フォアグラウンドプロセスとして動かし続けたくない場合は、
cron や systemd timer から都度 `python -m threads_ops secretary` を呼び出す方法もあります:

```cron
# 毎日 9:00 に秘書部門のサイクルを1回実行(下書きが data/drafts/pending/ に溜まる)
0 9 * * * cd /path/to/repo && .venv/bin/python -m threads_ops secretary --topics 3 --count 2 >> secretary.log 2>&1
```

## テスト

```bash
pytest -q
```

## ディレクトリ構成

```
threads_ops/       パイプライン本体
  config.py         環境変数ベースの設定
  models.py         CompetitorPost / ResearchReport / MarketingPlan / StrategyPlan / RevenueReport / CompanyReport / Draft
  research.py        [リサーチ部門] 競合データ分析
  marketing.py        [マーケティング部門] トーン・頻度・ハッシュタグ戦略の立案
  strategy.py          [戦略部門] コンテンツの柱・優先トピック・KPI目標の決定
  finance.py            [収益管理部門] KPI目標と投稿実績から見込み利益を試算
  affiliate.py           楽天アフィリエイト: 困りごと→商品カテゴリ→リンク生成
  secretary.py            [秘書部門] 各部門を統括して一括実行(定期ループ対応)し会社レポートを作成
  draft.py            下書き生成 (テンプレート / Anthropic、マーケティングプランのトーンを反映)
  approval.py       CLI 承認フロー
  publish.py         投稿 (Mock / 実 API)
  cli.py            コマンド群
data/
  competitors/      競合データ(自分で用意、現在は子育てジャンル)
  samples/          ジャンル非依存のフォーマット例(research の集計対象外)
  reports/          生成されたリサーチレポート
  marketing/        マーケティングプラン
  strategy/         戦略プラン
  finance/          収益レポート(見込み利益の試算)
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
- 収益管理部門(`finance.py`)が出す数値はすべて `.env` で設定した単価に基づく
  試算(見込み)であり、実際の広告収益・アフィリエイト成果などを計測しているわけ
  ではありません。実際の収益データと連携する仕組みは未実装です。
- `secretary --loop` はフォアグラウンドで動き続けるプロセスです。ターミナルを
  閉じると停止するため、常時稼働させたい場合は cron / systemd timer / プロセス
  マネージャ(systemd, supervisor 等)と組み合わせてください。
- `RAKUTEN_AFFILIATE_ID` が未設定の間、`affiliate.build_affiliate_link` が返すのは
  素の楽天市場検索リンクで、クリックされても収益は発生しません。実際に収益化するには
  [楽天アフィリエイト](https://affiliate.rakuten.co.jp/) の審査を通過してIDを取得し、
  `.env` に設定してください。紹介する商品もカテゴリの提案に留まるため、実在の商品を
  投稿前に選定する必要があります。
