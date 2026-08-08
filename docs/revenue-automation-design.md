# 設計提案: スレッズ以外での収益自動化

## 0. 位置づけ

このドキュメントは実装前の設計提案です。まだコードの変更は行っていません。
「対象プラットフォーム」「収益化の手段」「実データ連携の範囲」は意思決定が
必要な論点として本文中に明示しています(§5)。合意が取れた時点で、本提案を
たたき台に実装フェーズに入ります。

## 1. 現状整理

現在の `threads_ops` は Threads 専用の**運用自動化**パイプラインです。

```
research(競合分析) → draft(下書き生成) → review(人による承認) → publish(投稿)
```

- `models.py`: `CompetitorPost` / `ResearchReport` / `Draft` — いずれも
  Threads を前提にしたフィールド構成(文字数上限 500、Threads API の
  投稿フローなど)。
- `draft.py`: `DraftGenerator` Protocol(`TemplateDraftGenerator` /
  `AnthropicDraftGenerator`)はプラットフォーム非依存で書けているが、
  `config.THREADS_MAX_CHARS` に直接依存している。
- `publish.py`: `Publisher` Protocol(`MockPublisher` / `ThreadsAPIPublisher`)
  はインターフェース自体は汎用的だが、実装は Threads Graph API 専用。
- `approval.py`: 人間承認 CLI。Draft のみに依存しており、プラットフォーム
  非依存にできる設計。
- **収益化(マネタイズ)の概念がどこにも存在しない。** 現状のパイプライン
  は「投稿を自動生成して人が承認して出す」までで完結しており、アフィリエ
  イトリンクや広告収益、コンバージョン計測は範囲外。

→ 今回のゴールは (a) Threads 以外のプラットフォームに対応すること、
(b) 単なる投稿自動化ではなく「収益」につながる要素を組み込むこと、の2軸。
この2つは独立した拡張なので、別々の設計変更として扱う。

## 2. 全体アーキテクチャ方針

`threads_ops` を「Threads 専用パッケージ」から「共通コア + プラットフォーム
アダプタ」構成に分離する。

```
revenue_ops/
  core/
    models.py        # SourcePost / ResearchReport / Draft (platform非依存 + 収益フィールド)
    research.py       # 汎用アナライザ(現 research.py からThreads固有部分を除去)
    draft.py           # DraftGenerator Protocol + Template/Anthropic実装(既存を移設)
    approval.py       # 人間承認CLI(既存をほぼそのまま移設。Draftのみに依存)
    monetization.py   # NEW: MonetizationStrategy Protocol
    publish.py         # Publisher Protocol + MockPublisher(既存を移設)
    revenue.py         # NEW: 収益データの取り込み・集計
    storage.py         # 既存をそのまま移設
    config.py          # 共通設定 + プラットフォーム別設定のロード

  platforms/
    threads/
      platform.py     # Platform定義(max_chars=500 等) + ThreadsAPIPublisher(既存を移設)
    x/
      platform.py     # NEW: X (Twitter) 用 Publisher/設定
    note/              # または blog/ (§5で決定)
      platform.py     # NEW: note/ブログ用 Publisher/設定

  cli.py               # --platform フラグ対応の統合CLI
```

`threads_ops` はそのまま `platforms/threads` + `core` の再エクスポートとして
残し、既存の `python -m threads_ops ...` コマンドと `data/` 配下の
互換性を壊さない(後方互換のシムとして薄く残す)。

### Platform 抽象

```python
class Platform(Protocol):
    name: str            # "threads" / "x" / "note"
    max_chars: int | None
    supports_links: bool  # 本文中にリンクを直接貼れるか(Threadsはリンク埋め込み可、X同様)

    def publisher(self) -> Publisher: ...
    def draft_generator(self) -> DraftGenerator: ...
```

`draft`/`publish` コマンドは `--platform threads|x|note` を受け取り、対応する
`Platform` 実装を解決する。プラットフォームごとの投稿先ディレクトリは
`data/<platform>/drafts/{pending,approved,rejected,posted}` に分離し(Threads
は既存の `data/drafts/...` を後方互換で維持)、`Draft` に `platform: str`
フィールドを追加する。

## 3. 収益化(マネタイズ)レイヤーの追加

`draft` と `publish` の間に **monetize** ステージを新設する(承認前に適用し、
人間はマネタイズ要素込みの最終文面を確認してから承認する)。

```
research → draft → monetize → review(人による承認) → publish
```

```python
class MonetizationStrategy(Protocol):
    name: str
    def apply(self, draft: Draft, report: ResearchReport) -> Draft: ...
```

想定する実装(どれを採用するかは §5 で決定):

- `AffiliateLinkInjector`: `data/affiliate_links.json` などにトピック→ASP
  リンクの対応表を用意し、下書き本文の文脈に応じてリンクと開示文
  (「#PR」等、景品表示法・各ASP規約対応の表記)を挿入する。
- `ServiceCTAInjector`: 自社サービス/LP/note記事へのリンクと固定CTA文言を
  末尾に追加する。
- `EngagementOptimizedSelector`: リサーチレポートの `best_hours_utc` /
  `top_keywords` を使い、広告収益(インプレッション収益)に有利な
  エンゲージメント最適化のみを行う(リンク追加なし)。
- `NoOpMonetization`: 既定値。現行の Threads 運用と完全互換(何もしない)。

`Draft` モデルに以下を追加:

```python
platform: str = "threads"
monetization: str | None = None       # 適用したストラテジー名
revenue_links: list[str] = field(default_factory=list)
utm_tags: dict[str, str] = field(default_factory=dict)  # 効果測定用
```

## 4. 収益レポーティング

投稿の「生成・承認・投稿」を自動化しても、実際の収益(アフィリエイト成果
報酬・広告収益)は各ASP/広告ネットワークの管理画面側で確定するため、完全
自動取得は現実的に難しいプラットフォームが多い(§5で個別に要確認)。まずは
**手動/定期エクスポートしたCSVを取り込んで集計するレポーター**を用意する。

```
data/revenue/
  imports/            # ASP・広告ネットワークからエクスポートしたCSV/JSON
  reports/            # 集計済みレポート(投稿×収益の紐付け)
```

`core/revenue.py`:
- `RevenueRecord`: `post_id`, `platform`, `source`(ASP名など), `amount`,
  `currency`, `occurred_at`
- `link_to_posts(records, history) -> RevenueReport`: `utm_tags` / `post_id`
  をキーに `history.jsonl`(投稿履歴)と突き合わせ、プラットフォーム別・
  投稿別・monetization戦略別の収益サマリを作る。
- `python -m revenue_ops revenue-report` コマンドで実行し、既存の
  `research` コマンドと同様に JSON レポートを `data/revenue/reports/` に
  保存する。

将来的にASP側にAPIがあれば `RevenueSource` Protocol を追加して自動取り込み
に差し替え可能な設計にしておく(今回はCSV取り込みのみを実装範囲とする)。

## 5. 決定が必要な論点(オープンイシュー)

実装に入る前に、以下を決めていただく必要があります。

1. **対象プラットフォームの優先順位**
   候補: X (Twitter) / note / 汎用ブログ(WordPress等) / YouTube概要欄
   それぞれ収益化との相性が異なる:
   - X: 収益化プログラム(広告収益分配)はインプレッション連動、API利用
     コストが高い(有料プラン必須)。
   - note: 記事に自然にアフィリエイトリンクを埋め込みやすく、有料記事
     機能もあるが、公式APIは限定的(下書き投稿の可否要確認)。
   - ブログ(自社/WordPress): API連携は容易(REST API)、アフィリエイト
     やアドセンスとの相性が最も良いが、集客(SEO)は別途必要。
   最初の1プラットフォームをどれにするかで実装の第一歩が変わる。

2. **収益化の手段(§3の4方式)のうちどれを最初に作るか**
   アフィリエイト挿入は最も「収益自動化」らしいが、ASPごとの規約(自動
   生成文への広告表記義務など)を踏まえた運用ルール整備が要る。広告収益
   最適化(エンゲージメント狙い)は最もリスクが低く実装コストも低い。

3. **収益データの取得方法**
   完全自動連携が可能なASP/広告ネットワークがあるか(APIキー等の認証情報
   を用意できるか)、それとも手動CSVインポート運用で十分か。

4. **投稿の自動度合い**
   現行 Threads パイプラインと同様「人間が最終承認してから投稿」を維持す
   るか、それとも一部(例: エンゲージメント最適化のみ)は完全自動化するか。

## 6. 実装ロードマップ案(合意後)

1. **Phase 1 — リファクタリングのみ(挙動変更なし)**
   `threads_ops` を `core/` + `platforms/threads/` に分離。既存テスト
   (`tests/`)がグリーンのまま通ることを確認。
2. **Phase 2 — monetize ステージの追加**
   `NoOpMonetization` を既定にしたまま `monetize` ステージをパイプラインに
   組み込み、既存の Threads 運用に影響がないことを確認。
3. **Phase 3 — 決定したマネタイズ手段を1つ実装**
   オフラインで完結するもの(例: `AffiliateLinkInjector` をローカルJSONの
   対応表ベースで)から着手。
4. **Phase 4 — 決定した2つ目のプラットフォームを追加**
   Mock Publisher から着手し、実API連携はオプトインにする(Threadsと同じ
   安全設計を踏襲)。
5. **Phase 5 — 収益レポーティング**
   CSV取り込み → 投稿との突き合わせ → レポート生成。
6. **Phase 6 — 運用の定期実行化**
   cron/スケジューラでの `run-all` 相当の自動実行(承認ステップは人間が
   残る前提)。

## 7. 非目標(スコープ外として明示)

- 各プラットフォームの規約に反する自動スクレイピング・自動フォロー等の
  グロースハック行為は対象外(Threadsの既存方針を踏襲)。
- 広告収益・アフィリエイト成果の完全自動集計(ASP側API次第で将来対応)。
- 人間の承認を経ない完全自動投稿(§5-4の合意によって将来検討)。
