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
PRODUCT_CATALOG: dict[str, dict] = {
    "夜泣き": {"name": "ホワイトノイズマシン", "keyword": "ホワイトノイズマシン 赤ちゃん", "price_jpy": 3480},
    "寝かしつけ": {"name": "スワドルおくるみ", "keyword": "スワドル おくるみ", "price_jpy": 2680},
    "離乳食": {"name": "離乳食調理セット", "keyword": "離乳食 調理セット", "price_jpy": 3280},
    "イヤイヤ期": {"name": "気持ちが学べる絵本", "keyword": "育児 絵本 感情", "price_jpy": 1200},
    "お出かけ": {"name": "抱っこ紐", "keyword": "抱っこ紐", "price_jpy": 8900},
    "授乳": {"name": "授乳クッション", "keyword": "授乳クッション", "price_jpy": 3980},
    "鼻水": {"name": "電動鼻水吸引器", "keyword": "電動鼻水吸引器", "price_jpy": 5980},
    "後追い": {"name": "折りたたみベビーサークル", "keyword": "折りたたみ ベビーサークル", "price_jpy": 5480},
    "時短家事": {"name": "食洗機", "keyword": "食洗機", "price_jpy": 25000},
    "沐浴": {"name": "沐浴チェア", "keyword": "沐浴チェア", "price_jpy": 2980},
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
    }
