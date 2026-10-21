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

### 5. 過去の投稿を取得して仕分け

```bash
python -m threads_ops fetch-history            # 自分の全投稿 + インサイトを取得
python -m threads_ops fetch-history --since 2026-01-01 --limit 200
python -m threads_ops classify                 # カテゴリ別に仕分け
```

`fetch-history` は公式 API (`GET /me/threads`) で **自分のアカウントの** 過去投稿をページ送りしながら全件取得し、
各投稿のインサイト(閲覧数・いいね・返信・リポスト・引用)も取得して `data/my_posts/posts.json` に保存します。
`THREADS_ACCESS_TOKEN` が必要で、トークンには `threads_basic`(投稿取得)と
`threads_manage_insights`(インサイト。無い場合は `--no-insights`)の権限が必要です。読み取り専用で、投稿は一切行いません。

`classify` は各投稿をアカウントのコンセプト(育児の"困った"を、モノとアイデアで5分ラクにする)に照らして
**残す / 手直し / 削除候補** に仕分けし、理由も付けます。

| 判定 | 条件 |
|------|------|
| 削除候補 | 電話番号・メール・郵便番号・番地・園や学校の名前など、個人情報らしきものを含む / テーマとの関係が見当たらない |
| 手直し | テーマのキーワードが1つだけ(つながりが弱い) |
| 残す | テーマのキーワードが2つ以上 |

あわせて投稿の柱(困り事→解決 / 0円アイデア / 買ってよかった / 質問・アンケート / その他)も付けます。
出力は `data/my_posts/sorted/` に、判定ごとの JSON(エンゲージメント順)、`summary.json`、
確認用チェックリスト `棚卸し.md` です。**削除は自動では行いません**。チェックリストを見て、人が判断してください。
キーワードを変えたい場合は `data/my_posts/classify_rules.json` に
`{"theme_keywords": [...], "categories": {"柱の名前": [...]}}`(どちらも省略可)を置きます。

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
