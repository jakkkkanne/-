# Etsy 日本テーマ デジタル商品

Threads自動化プロジェクトとは別の、Etsy販売用デジタル商品の制作ブランチです。

## 優先商品
| フォルダ | 商品 | 状態 |
|---|---|---|
| `products/01-eto` | 干支12種セット・未年単品・家族の干支名入れポスター | 12種完成、名入れ生成OK |
| `products/03-business-etiquette` | 日本ビジネスマナー チートシート(US Letter 4ページ) | 完成(テスト販売用) |
| `products/04-japan-signs-drill` | Read Japan in 14 Days(看板を読む日本語ドリル) | 表紙+Day1-2見本、写真待ち |
| `products/listings.md` | Etsyのタイトル・タグ・説明文 | |

## 資料
- `personas.md` — ペルソナ(キャサリン/チャーリー)
- `product-ideas.md` — ペルソナ別商品アイデア
- 旧サンプル: `01_year_of_sheep_2027` / `02_hiragana_workbook` / `03_sashiko_patterns`(刺し子は保留)

## 作り方
```
node tools/render.js <html> <out.pdf> [プレビュー画像の接頭辞] [クエリ]
node tools/shot.js tools/mockup.html <out.png> "img=...&label=タイトル|サブ&badge=..."
```
`previews/` に各ページのPNGとEtsy用サムネイル(`previews/mockups/`)があります。
