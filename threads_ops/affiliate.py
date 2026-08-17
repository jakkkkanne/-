"""Affiliate monetization (Rakuten).

Maps a common parenting pain point to a Rakuten Ichiba product-search
keyword and builds a shareable link. Generating a link that actually earns
commission requires a real RAKUTEN_AFFILIATE_ID, issued by Rakuten
Affiliate (https://affiliate.rakuten.co.jp/) once your application is
approved -- there's no way around that from code. Without one,
build_affiliate_link falls back to a plain, unmonetized Rakuten Ichiba
search link plus a clear note, so drafts are never silently shipped with a
link nobody gets paid for.
"""

from __future__ import annotations

from urllib.parse import quote, quote_plus

from . import config

# Pain point -> product info. Deliberately generic product categories
# rather than specific brands/models: pick an actual product yourself
# before publishing. price_jpy is a rough market price used by the
# レン (finance) price-band filter (config.AFFILIATE_MIN_PRICE_JPY /
# AFFILIATE_MAX_PRICE_JPY) -- some categories (e.g. a real dishwasher) are
# realistically priced outside a small-ticket-item range on purpose, so the
# filter can honestly exclude them rather than fabricate a fake cheap price.
#
# review_count / reviews are hand-curated stand-ins for real review mining.
# アヤ was asked to pull live Rakuten/Amazon ranking + review data, but this
# session can't reach either -- neither the ranking page (blocked by
# Rakuten's own Akamai bot protection, same as the CLIENT_IP_NOT_ALLOWED
# issue on the official API) nor a scrape. These are illustrative example
# reviews for demonstrating ハル/カイ's pipeline, not real customer
# feedback; replace with actually-mined reviews once the Rakuten Ranking
# API (needs a Rakuten *Application* ID, separate from RAKUTEN_AFFILIATE_ID)
# is reachable from a stable-IP environment.
#
# brand_candidates (per entry, where アヤ found any): rough brand/product
# names surfaced via WebSearch as the current stand-in research method,
# per operator direction. These are search-engine snippet fragments, NOT a
# confirmed live ranking position, price, or review count -- WebFetch/curl
# to the actual ranking page returns Rakuten's Akamai anti-bot block from
# this environment, so there was no way to verify order or freshness.
# Treat them only as "roughly worth checking," never as ready-to-publish
# recommendations -- confirm on the real product page before using one to
# replace an entry's `name`/`price_jpy`, and note entries where no
# confident candidate turned up.
PRODUCT_CATALOG: dict[str, dict] = {
    "夜泣き": {
        "name": "ホワイトノイズマシン",
        "keyword": "ホワイトノイズマシン 赤ちゃん",
        "price_jpy": 3480,
        "review_count": 4200,
        "reviews": [
            {"pain": "抱っこしても寝てもすぐ起きて夜中に何度も起こされる", "resolution": "ホワイトノイズを流すようにしたら寝つきと寝続ける時間が伸びた"},
            {"pain": "夫婦交代で対応しても寝不足が限界だった", "resolution": "タイマー機能で朝まで自動で流せて対応の負担が減った"},
        ],
        # WebSearchでは具体的な機種名まで確度高く拾えなかった("レクトロファンマイクロ2"の
        # 言及はあったが、価格・現在の順位は未確認)。
        "brand_candidates": [],
    },
    "寝かしつけ": {
        "name": "スワドルおくるみ",
        "keyword": "スワドル おくるみ",
        "price_jpy": 2680,
        "review_count": 2900,
        "reviews": [
            {"pain": "布団に置いた瞬間に手足が動いて起きてしまう", "resolution": "おくるみで包むとモロー反射が抑えられて置いても起きにくくなった"},
            {"pain": "毎回同じ体勢で寝かしつけるのに時間がかかっていた", "resolution": "着せるだけで入眠の合図になり寝かしつけ時間が短縮した"},
        ],
        "brand_candidates": ["BRILBE(参考価格1,950円・参考レビュー12,166件)", "MARYPLUS マリープラス(参考価格1,990円〜・参考レビュー4,620件)"],
    },
    "離乳食": {
        "name": "離乳食調理セット",
        "keyword": "離乳食 調理セット",
        "price_jpy": 3280,
        "review_count": 1800,
        "reviews": [
            {"pain": "毎食すりつぶしたり裏ごししたりする手間が負担だった", "resolution": "1つの器具で潰す・こす・すりおろすができて調理時間が半分になった"},
            {"pain": "少量ずつしか作れず毎回洗い物が増えていた", "resolution": "まとめて作って冷凍保存する運用に切り替えられた"},
        ],
        # 見つかったのは保存容器・製氷皿など周辺グッズで、この項目の「潰す/こす/すりおろす
        # 一体型調理器具」とは商品カテゴリが一致しないため候補には入れていない。
        "brand_candidates": [],
    },
    "イヤイヤ期": {
        "name": "気持ちが学べる絵本",
        "keyword": "育児 絵本 感情",
        "price_jpy": 1200,
        "review_count": 3100,
        "reviews": [
            {"pain": "癇癪を起こした時にどう声をかけていいか分からなかった", "resolution": "絵本の言葉を借りて気持ちを代弁できるようになった"},
        ],
        "brand_candidates": [],
    },
    "お出かけ": {
        "name": "抱っこ紐",
        "keyword": "抱っこ紐",
        "price_jpy": 8900,
        "review_count": 5600,
        "reviews": [
            {"pain": "長時間の抱っこで腰と肩が限界だった", "resolution": "腰ベルトタイプに替えてから外出のハードルが下がった"},
            {"pain": "着脱に時間がかかって外出前にぐずられることが多かった", "resolution": "ワンタッチバックルで装着時間が短くなった"},
        ],
        # べべスワン(参考35,000円〜)/ベビービョルン ハーモニー(参考27,280円〜)/
        # ポルバン アドバンス ヒップシート(参考11,000円〜)は3件ともレンの価格帯
        # (1500〜10000円)を超えるため候補から除外。
        "brand_candidates": [],
    },
    "授乳": {
        "name": "授乳クッション",
        "keyword": "授乳クッション",
        "price_jpy": 3980,
        "review_count": 2400,
        "reviews": [
            {"pain": "授乳のたびに腕と腰が痛くなっていた", "resolution": "クッションで高さが安定し授乳中の負担が減った"},
        ],
        "brand_candidates": ["エルゴベビー ナチュラルカーブ ナーシングピロー(価格未確認)", "ロトトクッション(価格未確認・楽天721冠との言及あり)"],
    },
    "鼻水": {
        "name": "電動鼻水吸引器",
        "keyword": "電動鼻水吸引器",
        "price_jpy": 5980,
        "review_count": 6100,
        "reviews": [
            {"pain": "口で吸うタイプは自分にも風邪がうつって辛かった", "resolution": "電動タイプにしてから自分の体調を崩さずに済むようになった"},
            {"pain": "鼻水がひどい時期は夜中も何度も起きて対応していた", "resolution": "吸引時間が短くなり親子ともに睡眠の質が上がった"},
        ],
        # ピジョン「シュポット」(参考12,870円)とBabySmile「メルシーポット」S-504
        # (参考10,890円)は価格帯を超過。「ちぼじ」(参考3,980円)は手動式で
        # この項目の「電動」という前提と合わないため、いずれも候補から除外。
        "brand_candidates": [],
    },
    "後追い": {
        "name": "折りたたみベビーサークル",
        "keyword": "折りたたみ ベビーサークル",
        "price_jpy": 5480,
        "review_count": 1500,
        "reviews": [
            {"pain": "トイレや家事の間も後追いで泣かれて何もできなかった", "resolution": "安全な範囲を作ったことで数分だけ手が離せるようになった"},
        ],
        "brand_candidates": ["アイリスオーヤマ「ベビーアイランドDX 90199」(価格未確認)", "日本育児「Roomy+」(価格未確認)", "Hugmuu(価格未確認・ランキング2冠との言及あり)"],
    },
    "時短家事": {
        "name": "食洗機",
        "keyword": "食洗機",
        "price_jpy": 25000,
        "review_count": 8900,
        "reviews": [
            {"pain": "寝かしつけ後の洗い物が体力的にきつかった", "resolution": "食洗機に任せてから夜の自由時間が増えた"},
        ],
        "brand_candidates": [],
    },
    "沐浴": {
        "name": "沐浴チェア",
        "keyword": "沐浴チェア",
        "price_jpy": 2980,
        "review_count": 2100,
        "reviews": [
            {"pain": "片手で支えながら洗うのが不安定で毎回冷や汗をかいていた", "resolution": "チェアが体を支えてくれるので両手で洗えるようになった"},
        ],
        # ジャンル専用ランキングページは見つかったが、検索結果に具体的な商品名までは
        # 含まれなかった。
        "brand_candidates": [],
    },
}


def rakuten_search_url(keyword: str) -> str:
    # quote_plus renders spaces as "+" instead of "%20" -- multi-word
    # keywords stay slightly more readable when the link is shared as-is.
    return f"https://search.rakuten.co.jp/search/mall/{quote_plus(keyword)}/"


def build_affiliate_link(keyword: str) -> str:
    if not config.RAKUTEN_AFFILIATE_ID:
        return f"{rakuten_search_url(keyword)}(※RAKUTEN_AFFILIATE_ID未設定のため未収益化リンクです。.envに設定してください)"
    # Percent-encode the raw target exactly once here -- rakuten_search_url()
    # already returns an encoded URL, and re-encoding *that* would double-
    # escape every "%", which needlessly (~doubles) inflates link length and
    # eats into the 500-char post budget.
    raw_target = f"https://search.rakuten.co.jp/search/mall/{keyword}/"
    encoded = quote(raw_target, safe=":/")
    return f"https://hb.afl.rakuten.co.jp/hgc/{config.RAKUTEN_AFFILIATE_ID}/?pc={encoded}&m={encoded}"


def recommend_product(pain_point: str) -> tuple[str, str] | None:
    """Look up a product keyword + affiliate link for a pain point, if cataloged."""
    entry = PRODUCT_CATALOG.get(pain_point)
    if not entry:
        return None
    return entry["keyword"], build_affiliate_link(entry["keyword"])


def recommend_in_price_range(
    pain_point: str, min_price_jpy: int | None = None, max_price_jpy: int | None = None
) -> dict | None:
    """レン's price-banded product pick: name/keyword/price/link, or None if out of range.

    min/max default to config.AFFILIATE_MIN_PRICE_JPY / AFFILIATE_MAX_PRICE_JPY
    (either side may be unset, meaning no bound on that side).
    """
    entry = PRODUCT_CATALOG.get(pain_point)
    if not entry:
        return None

    min_price = config.AFFILIATE_MIN_PRICE_JPY if min_price_jpy is None else min_price_jpy
    max_price = config.AFFILIATE_MAX_PRICE_JPY if max_price_jpy is None else max_price_jpy
    price = entry["price_jpy"]
    if min_price is not None and price < min_price:
        return None
    if max_price is not None and price > max_price:
        return None

    return {
        "pain_point": pain_point,
        "name": entry["name"],
        "keyword": entry["keyword"],
        "price_jpy": price,
        "link": build_affiliate_link(entry["keyword"]),
        "review_count": entry.get("review_count", 0),
        "reviews": entry.get("reviews", []),
        # アヤがWebSearch経由で見つけた未検証のブランド候補(空の場合あり)。
        # 商品ページで確認するまでは name/price_jpy を置き換えないこと。
        "brand_candidates": entry.get("brand_candidates", []),
    }


def products_in_price_range(min_price_jpy: int | None = None, max_price_jpy: int | None = None) -> list[dict]:
    """All cataloged products within the price band, sorted by review_count desc.

    Sorting by review count is the same "口コミが多い順" ordering アヤ was asked
    to apply to real Rakuten/Amazon rankings; here it's applied to the
    curated catalog since live ranking data isn't reachable this session.
    """
    results = []
    for pain_point in PRODUCT_CATALOG:
        product = recommend_in_price_range(pain_point, min_price_jpy, max_price_jpy)
        if product:
            results.append(product)
    results.sort(key=lambda p: p["review_count"], reverse=True)
    return results
