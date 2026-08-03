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

### 2.5 1週間分をまとめて生成(探偵アカウント向け・ジャンル固定)

```bash
python -m threads_ops weekly-plan
```

1日6投稿 x 7日分(既定)の下書きを一括生成し、`data/drafts/pending/` に保存します。
このアカウントのジャンルは「妻に浮気(不倫)された30代男性が探偵事務所に調査を依頼する」
という実話風の連載に統一しており、`DetectiveDraftGenerator` が固定で使われます
(`ANTHROPIC_API_KEY` の有無に関わらず、`draft` コマンドのような汎用生成には
フォールバックしません)。

1日6投稿は1つの依頼(ケース)を次の6段階で描く構成です:

1. 依頼人紹介(30代の依頼人男性)
2. 相談内容(妻への違和感)
3. 調査方針
4. 調査開始(尾行)
5. 証拠の記録
6. 調査報告(結末)

依頼人の年齢や細部は日ごとに変えつつ、同じジャンル・同じ構成で1週間分(7ケース)を
生成します。

各下書きには `scheduled_at`(JST の投稿予定時刻)が付き、`publish` は予定時刻を
過ぎたものだけを投稿します。承認は前倒しでまとめて行っても、実際の投稿は
1日6件ずつ小出しになる、という運用が可能です(`publish` を毎日 cron 等で実行してください)。

オプション(`--topic` は下書きに記録するメタデータで、投稿本文には影響しません):

```bash
python -m threads_ops weekly-plan --posts-per-day 6 --days 7 --start-date 2026-08-04
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
  draft.py            下書き生成 (テンプレート / 探偵アカウント用 / Anthropic / 週次プラン)
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
