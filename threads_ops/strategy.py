"""Strategy department.

Combines the research report and marketing plan into a StrategyPlan: which
topics to prioritize, how many posts per week, and rough KPI targets. This
is what the secretary department hands to the draft stage.
"""

from __future__ import annotations

from . import config, storage
from .models import MarketingPlan, ResearchReport, StrategyPlan, now_iso


def _avg_engagement(report: ResearchReport) -> float:
    if not report.top_posts:
        return 0.0
    scores = [
        post.get("likes", 0) + post.get("replies", 0) * 2 + post.get("reposts", 0) * 3
        for post in report.top_posts
    ]
    return sum(scores) / len(scores)


def _pick_content_pillars(report: ResearchReport, top_n: int = 5) -> list[str]:
    # Hashtags are curated by the poster, so they make cleaner topic labels
    # than the free-text keyword tokenizer, which -- absent a Japanese
    # morphological analyzer -- turns unspaced Japanese sentences into a few
    # coarse multi-word chunks rather than real keywords (see research.py).
    if report.top_hashtags:
        return [h for h, _ in report.top_hashtags[:top_n]]
    if report.top_keywords:
        return [kw for kw, _ in report.top_keywords[:top_n]]
    return ["ブランド紹介"]


def build_strategy_plan(report: ResearchReport, marketing_plan: MarketingPlan) -> StrategyPlan:
    content_pillars = _pick_content_pillars(report)
    priority_topics = content_pillars[:3]

    kpi_targets = {
        "weekly_posts": marketing_plan.posting_cadence_per_week,
        "target_avg_engagement": round(_avg_engagement(report) * 1.1, 1),
        "target_follower_growth_pct": 5.0,
    }

    notes = (
        f"上位キーワード({', '.join(content_pillars)})を軸に、"
        f"週{marketing_plan.posting_cadence_per_week}件を目安に投稿する。"
    )

    return StrategyPlan(
        id=storage.new_id("strategy"),
        generated_at=now_iso(),
        source_report=report.id,
        source_marketing_plan=marketing_plan.id,
        content_pillars=content_pillars,
        priority_topics=priority_topics,
        weekly_post_target=marketing_plan.posting_cadence_per_week,
        kpi_targets=kpi_targets,
        notes=notes,
    )


def save_strategy_plan(plan: StrategyPlan, strategy_dir=None) -> str:
    strategy_dir = strategy_dir or config.STRATEGY_DIR
    path = strategy_dir / f"{plan.id}.json"
    storage.write_json(path, plan.to_dict())
    return str(path)


def latest_strategy_plan(strategy_dir=None) -> StrategyPlan | None:
    strategy_dir = strategy_dir or config.STRATEGY_DIR
    files = storage.list_json_files(strategy_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return StrategyPlan.from_dict(storage.read_json(latest))


def run_strategy(
    report: ResearchReport, marketing_plan: MarketingPlan, strategy_dir=None
) -> tuple[StrategyPlan, str]:
    plan = build_strategy_plan(report, marketing_plan)
    path = save_strategy_plan(plan, strategy_dir)
    return plan, path
