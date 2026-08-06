"""Marketing department.

Turns a ResearchReport into an actionable marketing plan: tone, posting
cadence, hashtag strategy and growth tactics. Deterministic and offline --
no external API calls, so it always works and is easy to test.
"""

from __future__ import annotations

from . import config, storage
from .models import MarketingPlan, ResearchReport, now_iso

AGENT_NAME = "ハル"  # マーケティング部門担当

_GROWTH_TACTICS = [
    "反応の良い時間帯(best_hours_utc)に投稿を集中させる",
    "上位ハッシュタグを毎回1〜2個添えてリーチを広げる",
    "リプライ欄で会話を続けてエンゲージメントを積み増す",
    "保存されやすい要約・リスト形式の投稿を増やす",
    "競合の高反応投稿のフォーマットを参考にする",
    "「解決法」投稿には楽天アフィリエイト商品リンクを添えて収益に繋げる",
]


def build_marketing_plan(report: ResearchReport) -> MarketingPlan:
    if config.WEEKLY_POST_TARGET_OVERRIDE is not None:
        # An explicit business decision (e.g. "42 posts/week") wins over the
        # post_count-based heuristic below.
        cadence = config.WEEKLY_POST_TARGET_OVERRIDE
    elif report.post_count >= 20:
        cadence = 7
    elif report.post_count > 0:
        cadence = 3
    else:
        cadence = 1

    tone = "カジュアルで簡潔" if report.avg_post_length and report.avg_post_length < 150 else "詳しく丁寧"
    tactic_count = 4 if report.post_count >= 10 else 2

    return MarketingPlan(
        id=storage.new_id("marketing"),
        generated_at=now_iso(),
        source_report=report.id,
        target_keywords=[kw for kw, _ in report.top_keywords[:8]],
        hashtag_strategy=[f"#{h}" for h, _ in report.top_hashtags[:5]],
        best_hours_utc=report.best_hours_utc[:3],
        tone=tone,
        posting_cadence_per_week=cadence,
        growth_tactics=_GROWTH_TACTICS[:tactic_count],
    )


def save_marketing_plan(plan: MarketingPlan, marketing_dir=None) -> str:
    marketing_dir = marketing_dir or config.MARKETING_DIR
    path = marketing_dir / f"{plan.id}.json"
    storage.write_json(path, plan.to_dict())
    return str(path)


def latest_marketing_plan(marketing_dir=None) -> MarketingPlan | None:
    marketing_dir = marketing_dir or config.MARKETING_DIR
    files = storage.list_json_files(marketing_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return MarketingPlan.from_dict(storage.read_json(latest))


def run_marketing(report: ResearchReport, marketing_dir=None) -> tuple[MarketingPlan, str]:
    plan = build_marketing_plan(report)
    path = save_marketing_plan(plan, marketing_dir)
    return plan, path
