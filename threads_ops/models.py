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
    hashtags: list[str] = field(default_factory=list)

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
            hashtags=data.get("hashtags", []),
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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchReport":
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
