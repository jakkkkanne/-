"""Data structures shared across the research/draft/approval/publish stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CompetitorPost:
    account: str
    text: str
    posted_at: str  # ISO-8601
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    views: int = 0
    hashtags: list[str] = field(default_factory=list)
    # Manually tagged post format, e.g. "あるある" / "困りごと" / "解決法".
    # Optional -- populated by whoever curates data/competitors/*.json.
    post_type: str | None = None

    def engagement_score(self) -> float:
        return self.likes + self.replies * 2 + self.reposts * 3

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CompetitorPost":
        return cls(
            account=data["account"],
            text=data["text"],
            posted_at=data["posted_at"],
            likes=data.get("likes", 0),
            replies=data.get("replies", 0),
            reposts=data.get("reposts", 0),
            views=data.get("views", 0),
            hashtags=data.get("hashtags", []),
            post_type=data.get("post_type"),
        )


@dataclass
class ResearchReport:
    id: str
    generated_at: str
    accounts_analyzed: list[str]
    post_count: int
    top_keywords: list[list]  # list of [keyword, count]
    top_hashtags: list[list]  # list of [hashtag, count]
    best_hours_utc: list[list]  # list of [hour, avg_engagement]
    avg_post_length: float
    top_posts: list[dict]  # highest-engagement CompetitorPost dicts, for reference
    viral_post_count: int = 0  # posts at/above config.MIN_VIRAL_VIEWS
    viral_avg_views: float = 0.0
    patterns_by_type: dict = field(default_factory=dict)  # post_type -> stats dict

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchReport":
        return cls(**data)


@dataclass
class MarketingPlan:
    """Marketing department output: how to package the research findings."""

    id: str
    generated_at: str
    source_report: str
    target_keywords: list[str]
    hashtag_strategy: list[str]
    best_hours_utc: list[list]
    tone: str
    posting_cadence_per_week: int
    growth_tactics: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MarketingPlan":
        return cls(**data)


@dataclass
class StrategyPlan:
    """Strategy department output: what to post about, how often, and why."""

    id: str
    generated_at: str
    source_report: str
    source_marketing_plan: str
    content_pillars: list[str]
    priority_topics: list[str]
    weekly_post_target: int
    kpi_targets: dict
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyPlan":
        return cls(**data)


@dataclass
class RevenueReport:
    """Finance department output: a weekly profit projection.

    All monetary figures are estimates derived from the strategy
    department's KPI targets and configurable monetization rates (see
    config.py) -- not measured revenue. Treat this as a planning aid, not
    accounting.
    """

    id: str
    generated_at: str
    source_strategy_plan: str
    posts_published_total: int
    weekly_post_target: int
    estimated_weekly_engagement_value: float
    estimated_weekly_follower_value: float
    estimated_weekly_affiliate_revenue: float
    estimated_weekly_generation_cost: float
    estimated_weekly_profit: float
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RevenueReport":
        return cls(**data)


@dataclass
class CompanyReport:
    """Secretary department output: a run summary across all departments."""

    id: str
    generated_at: str
    research_report_id: str
    marketing_plan_id: str
    strategy_plan_id: str
    finance_report_id: str
    department_summaries: dict[str, str]
    draft_ids: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CompanyReport":
        return cls(**data)


@dataclass
class Draft:
    id: str
    topic: str
    text: str
    created_at: str
    status: str  # pending | approved | rejected | posted
    source_report: str | None = None
    generator: str = "template"
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Draft":
        return cls(**data)
