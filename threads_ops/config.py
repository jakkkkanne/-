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
    ):
        d.mkdir(parents=True, exist_ok=True)
