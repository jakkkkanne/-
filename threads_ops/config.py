"""Environment-driven configuration for the pipeline."""

import os
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


DATA_DIR = _env_path("THREADS_OPS_DATA_DIR", "data")
COMPETITORS_DIR = DATA_DIR / "competitors"
REPORTS_DIR = DATA_DIR / "reports"
DRAFTS_DIR = DATA_DIR / "drafts"
PENDING_DIR = DRAFTS_DIR / "pending"
APPROVED_DIR = DRAFTS_DIR / "approved"
REJECTED_DIR = DRAFTS_DIR / "rejected"
POSTED_DIR = DRAFTS_DIR / "posted"
HISTORY_FILE = DRAFTS_DIR / "history.jsonl"

# Company departments (built on top of the research/draft/review/publish pipeline)
MARKETING_DIR = DATA_DIR / "marketing"
STRATEGY_DIR = DATA_DIR / "strategy"
SECRETARY_DIR = DATA_DIR / "secretary"
FINANCE_DIR = DATA_DIR / "finance"

# Finance department: monetization assumptions used to project revenue from
# engagement/follower-growth KPI targets. These are rough placeholders --
# set them via .env to match your actual monetization model (affiliate
# payouts, lead value, ad revenue share, etc).
REVENUE_PER_ENGAGEMENT_POINT = float(os.environ.get("THREADS_OPS_REVENUE_PER_ENGAGEMENT", "3.0"))
REVENUE_PER_NEW_FOLLOWER = float(os.environ.get("THREADS_OPS_REVENUE_PER_FOLLOWER", "20.0"))
CURRENT_FOLLOWER_COUNT = int(os.environ.get("THREADS_OPS_FOLLOWER_COUNT", "0"))
COST_PER_DRAFT_GENERATED = float(os.environ.get("THREADS_OPS_COST_PER_DRAFT", "0.0"))

# Research: a post at/above this view count is treated as "viral" -- the
# research department analyzes these separately to find the format/pattern
# worth reproducing (see research.analyze()'s patterns_by_type).
MIN_VIRAL_VIEWS = int(os.environ.get("THREADS_OPS_MIN_VIRAL_VIEWS", "10000"))

# Marketing: when set, overrides the automatic post_count-based cadence
# heuristic with an explicit business decision (e.g. "42 posts/week").
_weekly_target_raw = os.environ.get("THREADS_OPS_WEEKLY_POST_TARGET")
WEEKLY_POST_TARGET_OVERRIDE = int(_weekly_target_raw) if _weekly_target_raw else None

# Rakuten affiliate monetization. RAKUTEN_AFFILIATE_ID is the ID issued by
# Rakuten Affiliate (https://affiliate.rakuten.co.jp/) once your application
# is approved -- there is no way to generate a working affiliate link without
# it, so affiliate.py falls back to an explicit placeholder when it's unset.
# The CTR/conversion/commission figures are planning assumptions, not
# measured data; tune them once you have real click/purchase numbers.
RAKUTEN_AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID", "")
ESTIMATED_WEEKLY_AFFILIATE_CLICKS = float(os.environ.get("THREADS_OPS_WEEKLY_AFFILIATE_CLICKS", "0"))
RAKUTEN_AVG_CONVERSION_RATE = float(os.environ.get("THREADS_OPS_RAKUTEN_CONVERSION_RATE", "0.03"))
RAKUTEN_AVG_COMMISSION_PER_SALE = float(os.environ.get("THREADS_OPS_RAKUTEN_COMMISSION_PER_SALE", "300.0"))

# レン's price band for affiliate product recommendations (JPY). Either side
# may be left unset (no bound). Business decision, not derived from data.
_affiliate_min_price_raw = os.environ.get("THREADS_OPS_AFFILIATE_MIN_PRICE_JPY")
_affiliate_max_price_raw = os.environ.get("THREADS_OPS_AFFILIATE_MAX_PRICE_JPY")
AFFILIATE_MIN_PRICE_JPY = int(_affiliate_min_price_raw) if _affiliate_min_price_raw else None
AFFILIATE_MAX_PRICE_JPY = int(_affiliate_max_price_raw) if _affiliate_max_price_raw else None

# "mock" never calls the real Threads API. "real" requires THREADS_ACCESS_TOKEN
# and THREADS_USER_ID and performs actual publish calls.
PUBLISHER_MODE = os.environ.get("THREADS_OPS_PUBLISHER", "mock")

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")
THREADS_API_BASE = os.environ.get("THREADS_API_BASE", "https://graph.threads.net/v1.0")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

THREADS_MAX_CHARS = 500


def ensure_dirs() -> None:
    for d in (
        COMPETITORS_DIR,
        REPORTS_DIR,
        PENDING_DIR,
        APPROVED_DIR,
        REJECTED_DIR,
        POSTED_DIR,
        MARKETING_DIR,
        STRATEGY_DIR,
        SECRETARY_DIR,
        FINANCE_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
