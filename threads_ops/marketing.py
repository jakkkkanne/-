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


def predict_trending_format(report: ResearchReport) -> tuple[str | None, str | None, str]:
    """ハル's read on アヤ's text-only viral data: which post_type keeps growing,
    and which one resonates most with the audience.

    - predicted_trending_type: highest avg_views among text_only_patterns_by_type
      (reach signal -- what's currently getting seen the most).
    - target_resonant_type: highest avg_replies (engagement-depth signal --
      what actually gets the audience talking, not just scrolling past).
    They can be the same type or different; when different that's worth
    calling out explicitly, since it means "what spreads" and "what
    resonates" aren't the same post right now.
    """
    patterns = report.text_only_patterns_by_type
    if not patterns:
        return None, None, "バイラル(文章のみ)データが不足しているため型の予測はできません。"

    predicted_type = max(patterns, key=lambda t: patterns[t]["avg_views"])
    resonant_type = max(patterns, key=lambda t: patterns[t]["avg_replies"])

    if predicted_type == resonant_type:
        rationale = (
            f"「{predicted_type}」が平均閲覧数{patterns[predicted_type]['avg_views']}・"
            f"平均返信数{patterns[predicted_type]['avg_replies']}とも最も高く、"
            "伸びと共感の両方でターゲット層に刺さっている型です。"
        )
    else:
        rationale = (
            f"「{predicted_type}」は平均閲覧数{patterns[predicted_type]['avg_views']}で最も伸びていますが、"
            f"「{resonant_type}」は平均返信数{patterns[resonant_type]['avg_replies']}で"
            "ターゲット層との会話が最も生まれている型です。両方を織り交ぜるのがおすすめです。"
        )
    return predicted_type, resonant_type, rationale


def analyze_product_reviews(product: dict) -> dict:
    """ハル's read on one product's reviews: the primary pain -> resolution story.

    `product` is shaped like affiliate.recommend_in_price_range()'s return
    value (needs "reviews"/"name"/"review_count"). The curated review list
    is already ordered by representativeness, so the first entry is used
    as the lead angle for カイ's thread; the rest stay available as
    alternate angles.
    """
    reviews = product.get("reviews", [])
    if not reviews:
        return {
            "pain": None,
            "resolution": None,
            "insight": f"{product.get('name', 'この商品')}の口コミデータがまだありません。",
            "alternate_reviews": [],
        }
    primary = reviews[0]
    insight = f"「{primary['pain']}」という悩みが「{primary['resolution']}」で解決された、という声が中心。"
    return {
        "pain": primary["pain"],
        "resolution": primary["resolution"],
        "insight": insight,
        "alternate_reviews": reviews[1:],
    }


def analyze_products(products: list[dict]) -> list[dict]:
    """Batch version: attach ハル's review_insight to each product, unchanged otherwise."""
    return [{**product, "review_insight": analyze_product_reviews(product)} for product in products]


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
    predicted_type, resonant_type, rationale = predict_trending_format(report)

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
        predicted_trending_type=predicted_type,
        target_resonant_type=resonant_type,
        trend_rationale=rationale,
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
