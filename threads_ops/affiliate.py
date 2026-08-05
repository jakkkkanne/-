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

# Pain point -> Rakuten Ichiba search keyword. Deliberately generic product
# categories rather than specific brands/models: pick an actual product
# yourself before publishing, this just points at the right search results.
PRODUCT_CATALOG: dict[str, str] = {
    "夜泣き": "ホワイトノイズマシン 赤ちゃん",
    "寝かしつけ": "スワドル おくるみ",
    "離乳食": "離乳食 調理セット",
    "イヤイヤ期": "育児 絵本 感情",
    "お出かけ": "抱っこ紐",
    "授乳": "授乳クッション",
    "鼻水": "電動鼻水吸引器",
    "後追い": "ベビーサークル",
    "時短家事": "食洗機",
    "沐浴": "沐浴チェア",
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
    keyword = PRODUCT_CATALOG.get(pain_point)
    if not keyword:
        return None
    return keyword, build_affiliate_link(keyword)
