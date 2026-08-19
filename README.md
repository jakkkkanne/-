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

### 2.5 ペルソナ生成 → 1週間分の投稿生成(探偵アカウント向け)

このアカウント専用の2段階パイプラインです。どちらも Claude API を使うため
`ANTHROPIC_API_KEY` の設定が必須です(オフラインのフォールバックはありません)。

**a. ペルソナを作る(初回に1回)**

```bash
python -m threads_ops persona
```

固定の体験談(既定:「妻に不倫をされ探偵を雇い証拠を確保し慰謝料請求」)を、
共感のフック → どん底 → 転機 →変化 → メッセージ、という感情の流れを持つ
ストーリー投稿3パターンに変換し、`data/persona/persona.md` に保存します。
これがアカウントの「語り口の見本」になります。以後の `weekly-plan` は毎回
このファイルを読み込んで参考にします。作り直したい場合だけ再実行してください
(`--experience` / `--supplement` で体験の内容を変更可能)。

**b. 1週間分の投稿を作る(ペルソナ生成後、毎週)**

```bash
python -m threads_ops weekly-plan
```

保存済みのペルソナを参考に、テーマ「不倫する人の共通行動」・ジャンル「不倫された・
浮気された」・口調「やさしく、等身大で偉そうにせず、友達に語りかける様に」(いずれも
`--theme` / `--genre` / `--tone` で変更可)で、1日1投稿・週7本を生成します。
7本は必ず次の型を1つずつ使います:

1日目:悩み共感型 / 2日目:実体験型 / 3日目:ノウハウ型 / 4日目:逆張り型 /
5日目:数字提示型 / 6日目:質問型 / 7日目:まとめ型

各下書きには `scheduled_at`(既定 JST 08:00、`--post-time` で変更可)が付き、
`publish` は予定時刻を過ぎたものだけを投稿します。承認は前倒しでまとめて行っても、
実際の投稿は1日1件ずつ小出しになります(`publish` を毎日 cron 等で実行してください)。
`review` では各下書きの型と狙い(何のための投稿か)も表示されます。

```bash
python -m threads_ops weekly-plan --start-date 2026-08-24 --post-time 07:30
```

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
  draft.py            下書き生成 (テンプレート / Anthropic、`draft` コマンド用)
  persona.py          ペルソナ生成(プロンプト①、`persona` コマンド用)
  weekly.py            週次投稿生成(プロンプト②、`weekly-plan` コマンド用)
  approval.py       CLI 承認フロー
  publish.py         投稿 (Mock / 実 API、scheduled_at を尊重)
  cli.py            コマンド群
data/
  competitors/      競合データ(自分で用意)
  reports/          生成されたリサーチレポート
  persona/          生成済みペルソナ(persona.md)
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
