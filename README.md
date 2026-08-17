# Threads 運用会社 (threads_ops)

Threads (Meta) の運用を、複数SNS展開(X・Threads・Instagram・note)を見据えた
「運用会社」の第一弾として自動化するパイプラインです。会社は5部門で構成されます。

**現在の運用方針:** ジャンルは子育て(あるある・困りごと・解決法)に特化し、
閲覧数1万以上の競合投稿の「型」を分析して再現しつつ、商品ごとにツリー(スレッド)
投稿を作って収益化します。投稿頻度は週42件(1日6投稿)を公式カデンスとして運用します
(`.env` の `THREADS_OPS_WEEKLY_POST_TARGET`)。商品は楽天アフィリエイトの価格帯
1500〜10000円のものに絞り、投稿本文には URL ではなく `[商品名]` の角括弧表記のみを
使います。**投稿は自動publishせず、必ず運用者本人が内容を確認したうえで手動で
投稿します**(`THREADS_OPS_PUBLISHER` は既定で `mock` のままにしています)。

| 部門 | 担当 | 役割 | 対応モジュール |
| --- | --- | --- | --- |
| リサーチ部門 | アヤ | 競合投稿を分析しレポート化。閲覧数1万以上・文章のみの投稿を「バイラル投稿」として型(あるある/困りごと/解決法)ごとに分析し、曜日x時間帯ごとの反応も集計。楽天ランキングAPIから商品データを取得する経路も用意(動作確認済み、ただしIP許可リストの制約あり) | `research.py` / `rakuten_ranking.py` |
| マーケティング部門 | ハル | レポートから投稿トーン・頻度・ハッシュタグ戦略を立案し、アヤのデータから今後伸びる型・ターゲット層に刺さる型を予測。商品の口コミから悩み→解決のストーリーを分析 | `marketing.py` |
| 戦略部門 | カイ | コンテンツの柱・優先トピック・KPI目標を決定し、曜日x時間帯ごとの投稿カレンダーを作成。商品ごとに「冒頭フック→体験談→解決法」のツリー投稿下書きも作成 | `strategy.py` |
| 収益管理部門 | レン | KPI目標と投稿実績から週次の見込み利益を試算し、アフィリエイト商品の価格帯(現在1500〜10000円)を管理 | `finance.py` / `affiliate.py` |
| 秘書部門 | ミナ | 上記4部門を統括し、下書き生成まで一括実行してレポートを作成。納品前に誤字脱字・トーン統一・可読性の最終チェックも行う | `secretary.py` |

各部門の担当名は対応モジュールの `AGENT_NAME` で定義されており、CLI実行時の出力や
秘書部門の `CompanyReport.department_summaries` にも表示されます。

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
      "post_type": "解決法",
      "media_type": "text"
    }
  ]
}
```

`views`(閲覧数)・`post_type`(`あるある` / `困りごと` / `解決法` など、手動でタグ付け)・
`media_type`(`text` / `image` / `video` など、既定は `text`)はいずれも任意項目です。
`views` が `.env` の `THREADS_OPS_MIN_VIRAL_VIEWS`(既定 10,000)以上の投稿は
「バイラル投稿」として別集計され、`post_type` ごとに平均閲覧数・平均返信数・平均文字数・
冒頭パターンをまとめた `patterns_by_type` がレポートに含まれます。これが
「型を分析して再現する」の元データです。

さらに `media_type == "text"`(文章のみ)の投稿に限定して、
- `day_hour_performance`: 曜日x時間帯ごとの平均エンゲージメント(反応が良い曜日・時間帯の特定)
- `text_only_patterns_by_type`: 文章のみ・バイラルな投稿を型ごとに分析したもの

も算出します。**注意:** このリポジトリに同梱されているのは数日分のサンプルデータのみで、
何年分もの競合投稿履歴は保有していません。3年分などの長期リサーチをしたい場合は、
その期間の実データをご自身で `data/competitors/` に投入してください。データが多く
(特に曜日・時間帯のバリエーションが多く)なるほど `day_hour_performance` の精度が上がります。

実行:

```bash
python -m threads_ops research
```

キーワード・ハッシュタグの頻出度、反応が良い曜日・時間帯、平均文字数、バイラル投稿の型などを
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
Threads APIを使った自動投稿(`THREADS_OPS_PUBLISHER=real` + `THREADS_ACCESS_TOKEN` /
`THREADS_USER_ID`)も実装はされていますが、**現在の運用方針では使用しません**。
投稿は運用者本人が下書きを確認したうえで、Threadsアプリから手動で行ってください
(このリポジトリの `.env` は既定で `mock` のままにしています)。

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
さらにアヤの `text_only_patterns_by_type` を見て、`predicted_trending_type`(今後伸びると
予測する型、平均閲覧数が最も高い型)と `target_resonant_type`(ターゲット層に最も刺さって
いる型、平均返信数が最も高い型)を判定し、根拠を `trend_rationale` に記録します。

### 戦略部門

```bash
python -m threads_ops strategy
```

最新のレポート + マーケティングプランから、コンテンツの柱・優先トピック・
週次投稿目標・KPI目標(エンゲージメント/フォロワー成長率の目安)をまとめた
`StrategyPlan` を生成し `data/strategy/` に保存します。優先トピックは上位ハッシュタグ
(なければキーワード)から選ばれます(投稿の型を表すハッシュタグ、例:「#解決法」は
トピック候補から除外されます)。

`StrategyPlan.weekly_calendar` には、アヤの `day_hour_performance`(曜日x時間帯ごとの
実績)とハルの予測型を組み合わせた、曜日x時間帯ごとの投稿カレンダーが入ります。各枠は
`{day, hour, post_type, topic, product_name, notes}` の形式で、`notes` にはなぜその型・
時間帯・商品を選んだかという戦略意図(備考)が入ります。トピックが `affiliate.PRODUCT_CATALOG`
の困りごとに一致し、価格が価格帯内であれば `product_name` に商品名が入りますが、
**URLは入りません**(実際のリンクはレン=`affiliate.py`が別途管理します)。
1日あたりの投稿数(`posts_per_day`)は `週次投稿目標 / 7` から自動算出されます
(週42件なら1日6投稿)。

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
商品名・検索キーワード・想定価格(`price_jpy`)に対応させ、リンクを生成します
(`affiliate.PRODUCT_CATALOG` にカテゴリの一覧があります)。`.env` に
`RAKUTEN_AFFILIATE_ID`([楽天アフィリエイト](https://affiliate.rakuten.co.jp/)の
審査通過後に発行されるID)を設定すると実際に収益化されるリンクを生成し、
未設定の場合は素の楽天市場検索リンク(収益化されない)にフォールバックします。
商品は具体的なブランド・型番ではなくカテゴリ単位で提案しているので、実際に紹介する
商品は投稿前に選定してください。

**価格帯フィルタ:** `.env` の `THREADS_OPS_AFFILIATE_MIN_PRICE_JPY` /
`THREADS_OPS_AFFILIATE_MAX_PRICE_JPY`(現在は 1500〜10000円)を設定すると、
`affiliate.recommend_in_price_range(pain_point)` がその価格帯内の商品だけを返します。
戦略部門(カイ)の週間カレンダーもこの価格帯を使って商品を選ぶため、価格帯外の
商品(例: 食洗機のような高額品)は自動的に商品提案から除外されます
(投稿の型自体は作られ、`notes` に「該当価格帯の商品なし」と記録されます)。

**口コミ数・口コミ内容:** `affiliate.PRODUCT_CATALOG` の各商品には `review_count`
(口コミ数)と `reviews`(悩み→解決の例)も入っています。これらは手動キュレーションの
サンプルデータです。楽天・Amazonの実際のランキング/口コミを自動取得する仕組みは
まだ動いていません(下記「商品ツリー投稿」参照)。`affiliate.products_in_price_range()`
で価格帯内の商品を口コミ数が多い順に取得できます。

### 商品ツリー投稿(アヤ→ハル→カイ→レン→ミナ)

競合の投稿を分析する通常のリサーチとは別に、**商品ごとにツリー(スレッド)投稿を
作るワークフロー**があります。

```python
from threads_ops import affiliate, config, marketing, secretary, strategy

products = affiliate.products_in_price_range(config.AFFILIATE_MIN_PRICE_JPY, config.AFFILIATE_MAX_PRICE_JPY)  # レン: 価格帯フィルタ、口コミ数順
analyzed = marketing.analyze_products(products)  # ハル: 商品ごとに口コミから悩み→解決を分析
threads = strategy.build_product_threads(analyzed)  # カイ: 冒頭フック→体験談→解決法のツリー下書きを作成
flagged = secretary.qa_check_threads(threads)  # ミナ: 誤字脱字・トーン統一・可読性の最終チェック
```

各スレッドは3投稿(`segments`)で構成されます:

1. **冒頭フック** -- 悩みへの共感を引く一文
2. **体験談** -- 「私も/うちも」で始まる、友達に語りかけるトーンの経験談
3. **解決法** -- 悩みがどう解決したかと `[商品名]`(URLではなく商品名のみ)

`draft.visible_length()` は `[...]` で囲まれた部分を文字数カウントから除外するため、
`[商品名]` が入っていても投稿の実質文字数(500文字)判定には影響しません。
`secretary.qa_check_thread()` は、敬体とカジュアル口調の混在・連続した空白や句読点・
`[]` の対応漏れ・改行のない長文などを機械的にチェックします(誤字脱字そのものの完全な
自動検出はできないため、最終的な確認は人が行ってください)。

**トーンの基準:運営者本人の実アカウント。** 投稿を作るたびに毎回、口調や雰囲気は
運営者本人のThreadsアカウント(Threads APIで取得した実投稿162件を分析)を基準に
する方針です -- 柔らかく、親しみやすく、偉そうにせず、友達に語りかける様な口調。
具体的には、である/ます調を避けて短い行で改行を多く入れる、「私だけじゃないよね?」
のような読み手と同じ側に立つ問いかけで始める、締めは「〜した方がいい」ではなく
「〜してみてほしいな」のように誘う言い方にする、といった特徴です。
`strategy.py` の `_HOOK_TEMPLATES` / `_TESTIMONIAL_TEMPLATES` はこの分析結果に
合わせて調整済みです。

**アヤの本来の指示(楽天・Amazonの現在の上位60位を口コミ数順に取得)は、まだ
このリポジトリの実行環境からは完了できていません。** ただし調査の結果、いくつか
分かったことがあります。

- 楽天は2026年2月にウェブサービスAPIを移行しており、エンドポイントが
  `app.rakuten.co.jp` から `openapi.rakuten.co.jp` に変わり、`applicationId` に加えて
  `accessKey` も必須になりました(`RAKUTEN_APPLICATION_ID` / `RAKUTEN_ACCESS_KEY`、
  どちらもアフィリエイトIDとは別物で、[webservice.rakuten.co.jp](https://webservice.rakuten.co.jp/)
  でセットで発行されます)。`rakuten_ranking.py` はこの新仕様に対応済みで、
  Rakuten公式の「APIテストフォーム」で実際に動作確認もできました。
- ただしこの新APIは**アプリごとのIP許可リスト**を持っており、許可されていない
  IPからのリクエストは `CLIENT_IP_NOT_ALLOWED` で拒否されます。クラウドの実行環境は
  リクエストごとに発信IPが変わることがあり、単一IPの登録では安定して動作しません。
  **固定IPを持つ環境(自分のPC・固定IPサーバーなど)から実行してください。**
- Amazonには実用的なランキング取得APIが存在しないため未対応です。

それまでは `affiliate.PRODUCT_CATALOG` の手動キュレーションデータ(口コミ数・
口コミ内容も例示)で代替しています。

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
  rakuten_ranking.py    楽天ランキングAPIクライアント(動作確認済み、IP許可リストの制約あり)
  marketing.py        [マーケティング部門] トーン・頻度・ハッシュタグ戦略の立案、口コミ分析、型の予測
  strategy.py          [戦略部門] コンテンツの柱・優先トピック・KPI目標の決定、商品ツリー投稿の作成
  finance.py            [収益管理部門] KPI目標と投稿実績から見込み利益を試算
  affiliate.py           楽天アフィリエイト: 困りごと→商品カテゴリ(価格・口コミ含む)→リンク生成
  secretary.py            [秘書部門] 各部門を統括して一括実行(定期ループ対応)し、QAチェックも担当
  draft.py            下書き生成 (テンプレート / Anthropic、マーケティングプランのトーンを反映)。
                        visible_length/truncate_to_limit で [商品名] 表記を文字数から除外
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
- `research.py` の曜日x時間帯分析(`day_hour_performance`)や型分析
  (`text_only_patterns_by_type`)は、あくまで `data/competitors/` に投入したデータの
  範囲でしか計算できません。このリポジトリのサンプルデータは数日分のみで、何年分もの
  競合投稿履歴は保有していません。長期間(例: 3年分)のリサーチをしたい場合は、その
  期間の実データをご自身で用意して投入する必要があります。データが少ないと、多くの
  曜日x時間帯スロットが `best_hours_utc` からの補完(実績データなし)になります。
