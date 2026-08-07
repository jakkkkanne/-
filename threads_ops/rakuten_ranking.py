"""Rakuten Ichiba Ranking API client (アヤ's real-data path).

Fetches the current top-N ranked items in a genre from Rakuten's Ichiba
Item Ranking API, then re-sorts them by review count ("口コミが多い順"), per
the operator's instruction to アヤ. Until this is wired into the actual
research pipeline, affiliate.PRODUCT_CATALOG's hand-curated
review_count/reviews fields stand in for it.

STATUS (verified 2026-08): Rakuten migrated this API in Feb 2026 --
the endpoint moved from app.rakuten.co.jp to openapi.rakuten.co.jp, the
path prefix is "ichibaranking" (not "services"), and requests now need
BOTH an applicationId *and* an accessKey (two different credentials,
issued together per registered app at https://webservice.rakuten.co.jp/).
The exact request shape below was confirmed working via Rakuten's own
"APIテストフォーム" test tool -- it returned real ranking data.

However, this API also enforces a per-app IP allowlist
(CLIENT_IP_NOT_ALLOWED), and this session's outbound IP rotates on every
request (confirmed: three consecutive requests came from three different
IPs), so a cloud session like this one can't reliably be added to that
allowlist. fetch_ranking_page() will fail with CLIENT_IP_NOT_ALLOWED from
here -- run it instead from an environment with a stable IP (e.g. your own
machine or a fixed-IP server), after adding *that* IP in the app's
"許可されたIPアドレス" setting.

reviewCount as a field name is not yet confirmed against a full response
(only a truncated one was seen) -- double check it against your own
response before trusting rank_by_review_count()'s sort key.

There is no equivalent for Amazon: Amazon's Product Advertising API
requires an active Associates account with qualifying sales history, and
its bestseller/ranking data is not available through it in practice.
Scraping Amazon's site directly would violate its Terms of Service and is
out of scope, same as the no-scraping stance for Threads/competitor data.
"""

from __future__ import annotations

from . import config

RAKUTEN_RANKING_API = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"


def fetch_ranking_page(
    genre_id: str,
    application_id: str | None = None,
    access_key: str | None = None,
    page: int = 1,
) -> list[dict]:
    """Fetch one page (~30 items) of Rakuten's current ranking for a genre.

    Returns raw API item dicts, in Rakuten's own ranking order (not yet
    re-sorted by review count -- see rank_by_review_count).
    """
    import requests  # lazy import, same pattern as AnthropicDraftGenerator

    app_id = application_id or config.RAKUTEN_APPLICATION_ID
    key = access_key or config.RAKUTEN_ACCESS_KEY
    if not app_id or not key:
        raise RuntimeError(
            "RAKUTEN_APPLICATION_ID and RAKUTEN_ACCESS_KEY must both be set "
            "(issued together at https://webservice.rakuten.co.jp/ -- "
            "separate from RAKUTEN_AFFILIATE_ID)."
        )

    params = {
        "format": "json",
        "applicationId": app_id,
        "accessKey": key,
        "genreId": genre_id,
        "page": page,
    }
    response = requests.get(RAKUTEN_RANKING_API, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return [entry["Item"] for entry in data.get("Items", [])]


def fetch_top_ranked(
    genre_id: str,
    application_id: str | None = None,
    access_key: str | None = None,
    count: int = 60,
) -> list[dict]:
    """Page through the ranking until `count` raw items are collected."""
    items: list[dict] = []
    page = 1
    while len(items) < count:
        batch = fetch_ranking_page(genre_id, application_id, access_key, page=page)
        if not batch:
            break
        items.extend(batch)
        page += 1
    return items[:count]


def rank_by_review_count(items: list[dict], top_n: int = 60) -> list[dict]:
    """Re-sort raw ranking items by reviewCount desc (口コミが多い順)."""
    return sorted(items, key=lambda item: item.get("reviewCount", 0), reverse=True)[:top_n]
