"""Competitor research stage.

Meta's official Threads API only exposes data for the authenticated
account (publishing, replies, insights) -- it has no endpoint for reading
another account's posts. So competitor analysis here works off of local
JSON files that you populate yourself (e.g. manually recorded posts, or
an export you're entitled to use). Automated scraping of Threads is out
of scope: it isn't offered by the API and would risk violating the
platform's terms of service.

Drop one JSON file per competitor account into data/competitors/, each
containing a list of posts shaped like models.CompetitorPost, and `analyze`
will turn them into a ResearchReport.

Keyword extraction is a plain regex tokenizer (no Japanese morphological
analyzer such as MeCab/fugashi), so it works best on hashtags and
space-delimited terms; unsegmented running Japanese text will come out as
coarser multi-character chunks rather than individual words.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from . import config, storage
from .models import CompetitorPost, ResearchReport, now_iso

_HASHTAG_RE = re.compile(r"#(\w+)")
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on", "for",
    "and", "or", "it", "this", "that", "with", "as", "at", "by", "be", "we",
    "you", "your", "our", "i",
    "の", "は", "が", "を", "に", "で", "と", "も", "か", "です", "ます", "した",
    "する", "され", "これ", "それ", "あの", "この", "な", "だ", "ん", "こと",
    "から", "まで", "へ", "や", "ね", "よ", "し",
}


def load_competitor_posts(competitors_dir=None) -> list[CompetitorPost]:
    competitors_dir = competitors_dir or config.COMPETITORS_DIR
    posts: list[CompetitorPost] = []
    for path in storage.list_json_files(competitors_dir):
        data = storage.read_json(path)
        raw_posts = data if isinstance(data, list) else data.get("posts", [])
        for raw in raw_posts:
            posts.append(CompetitorPost.from_dict(raw))
    return posts


def _tokenize(text: str) -> list[str]:
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _hour_of(post: CompetitorPost) -> int | None:
    try:
        dt = datetime.fromisoformat(post.posted_at.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).hour
    except ValueError:
        return None


def analyze(posts: list[CompetitorPost], top_n: int = 15) -> ResearchReport:
    if not posts:
        return ResearchReport(
            id=storage.new_id("report"),
            generated_at=now_iso(),
            accounts_analyzed=[],
            post_count=0,
            top_keywords=[],
            top_hashtags=[],
            best_hours_utc=[],
            avg_post_length=0.0,
            top_posts=[],
        )

    keyword_counter: Counter[str] = Counter()
    hashtag_counter: Counter[str] = Counter()
    hour_engagement: dict[int, list[float]] = {}
    lengths: list[int] = []

    for post in posts:
        keyword_counter.update(_tokenize(post.text))
        hashtags = post.hashtags or _HASHTAG_RE.findall(post.text)
        hashtag_counter.update(h.lower() for h in hashtags)
        lengths.append(len(post.text))

        hour = _hour_of(post)
        if hour is not None:
            hour_engagement.setdefault(hour, []).append(post.engagement_score())

    best_hours = sorted(
        ((hour, sum(scores) / len(scores)) for hour, scores in hour_engagement.items()),
        key=lambda item: item[1],
        reverse=True,
    )

    top_posts = sorted(posts, key=lambda p: p.engagement_score(), reverse=True)[:5]

    return ResearchReport(
        id=storage.new_id("report"),
        generated_at=now_iso(),
        accounts_analyzed=sorted({p.account for p in posts}),
        post_count=len(posts),
        top_keywords=[[w, c] for w, c in keyword_counter.most_common(top_n)],
        top_hashtags=[[h, c] for h, c in hashtag_counter.most_common(top_n)],
        best_hours_utc=[[h, round(score, 2)] for h, score in best_hours],
        avg_post_length=round(sum(lengths) / len(lengths), 1),
        top_posts=[p.to_dict() for p in top_posts],
    )


def save_report(report: ResearchReport, reports_dir=None) -> str:
    reports_dir = reports_dir or config.REPORTS_DIR
    path = reports_dir / f"{report.id}.json"
    storage.write_json(path, report.to_dict())
    return str(path)


def latest_report(reports_dir=None) -> ResearchReport | None:
    reports_dir = reports_dir or config.REPORTS_DIR
    files = storage.list_json_files(reports_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return ResearchReport.from_dict(storage.read_json(latest))


def run_research(competitors_dir=None, reports_dir=None) -> tuple[ResearchReport, str]:
    posts = load_competitor_posts(competitors_dir)
    report = analyze(posts)
    path = save_report(report, reports_dir)
    return report, path
