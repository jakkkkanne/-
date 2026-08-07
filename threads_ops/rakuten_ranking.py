"""Rakuten Ichiba Ranking API client (アヤ's real-data path -- currently unusable here).

Meant to fetch the current top-N ranked items in a genre from Rakuten's
public Ichiba Item Ranking API, then re-sort them by review count ("口コミが
多い順"), per the operator's instruction to アヤ. Until that's wired up,
affiliate.PRODUCT_CATALOG's hand-curated review_count/reviews fields stand
in for this.

STATUS: written but unverified against a live response. This session's
network policy blocks app.rakuten.co.jp entirely (confirmed via the agent
proxy status -- CONNECT to app.rakuten.co.jp:443 was rejected), so this
module has never actually been exercised against the real API. Before
relying on it:
  1. Confirm network access to app.rakuten.co.jp is allowed for wherever
     this runs.
  2. Get a Rakuten *Application* ID from https://webservice.rakuten.co.jp/
     and set RAKUTEN_APPLICATION_ID -- this is a different credential from
     RAKUTEN_AFFILIATE_ID (that one builds monetized links; this one calls
     Rakuten's search/ranking APIs).
  3. Re-check the response shape against the current API docs
     (https://webservice.rakuten.co.jp/api/ichibaitemranking/) before
     trusting field names like reviewCount/itemName below.

There is no equivalent for Amazon: Amazon's Product Advertising API
requires an active Associates account with qualifying sales history, and
its bestseller/ranking data is not available through it in practice.
Scraping Amazon's site directly would violate its Terms of Service and is
out of scope, same as the no-scraping stance for Threads/competitor data.
"""

from __future__ import annotations

from . import config

RAKUTEN_RANKING_API = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"


def fetch_ranking_page(genre_id: str, application_id: str | None = None, page: int = 1) -> list[dict]:
    """Fetch one page (~30 items) of Rakuten's current ranking for a genre.

    Returns raw API item dicts, in Rakuten's own ranking order (not yet
    re-sorted by review count -- see rank_by_review_count).
    """
    import requests  # lazy import, same pattern as AnthropicDraftGenerator

    app_id = application_id or config.RAKUTEN_APPLICATION_ID
    if not app_id:
        raise RuntimeError(
            "RAKUTEN_APPLICATION_ID is not set. Get one from "
            "https://webservice.rakuten.co.jp/ (separate from RAKUTEN_AFFILIATE_ID)."
        )

    params = {"format": "json", "applicationId": app_id, "genreId": genre_id, "page": page}
    response = requests.get(RAKUTEN_RANKING_API, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return [entry["Item"] for entry in data.get("Items", [])]


def fetch_top_ranked(genre_id: str, application_id: str | None = None, count: int = 60) -> list[dict]:
    """Page through the ranking until `count` raw items are collected."""
    items: list[dict] = []
    page = 1
    while len(items) < count:
        batch = fetch_ranking_page(genre_id, application_id, page=page)
        if not batch:
            break
        items.extend(batch)
        page += 1
    return items[:count]


def rank_by_review_count(items: list[dict], top_n: int = 60) -> list[dict]:
    """Re-sort raw ranking items by reviewCount desc (口コミが多い順)."""
    return sorted(items, key=lambda item: item.get("reviewCount", 0), reverse=True)[:top_n]
