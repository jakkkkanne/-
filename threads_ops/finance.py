"""Finance department.

Projects a weekly profit estimate from the strategy department's KPI
targets (target engagement, target follower growth) and the publish
history, using configurable monetization rates (config.py). These figures
are planning estimates, not measured revenue -- there is no real payment
or analytics integration behind them. Tune the rates in .env to match
your actual monetization model once you have one.
"""

from __future__ import annotations

from . import config, storage
from .models import RevenueReport, StrategyPlan, now_iso


def load_publish_history(history_file=None) -> list[dict]:
    history_file = history_file or config.HISTORY_FILE
    return storage.read_jsonl(history_file)


def build_revenue_report(strategy_plan: StrategyPlan, history_entries: list[dict]) -> RevenueReport:
    posts_published_total = sum(1 for e in history_entries if e.get("success"))

    target_engagement = strategy_plan.kpi_targets.get("target_avg_engagement", 0.0)
    target_follower_growth_pct = strategy_plan.kpi_targets.get("target_follower_growth_pct", 0.0)

    estimated_weekly_engagement_value = (
        strategy_plan.weekly_post_target * target_engagement * config.REVENUE_PER_ENGAGEMENT_POINT
    )
    new_followers = config.CURRENT_FOLLOWER_COUNT * (target_follower_growth_pct / 100)
    estimated_weekly_follower_value = new_followers * config.REVENUE_PER_NEW_FOLLOWER
    estimated_weekly_affiliate_revenue = (
        config.ESTIMATED_WEEKLY_AFFILIATE_CLICKS
        * config.RAKUTEN_AVG_CONVERSION_RATE
        * config.RAKUTEN_AVG_COMMISSION_PER_SALE
    )
    estimated_weekly_generation_cost = strategy_plan.weekly_post_target * config.COST_PER_DRAFT_GENERATED

    estimated_weekly_profit = (
        estimated_weekly_engagement_value
        + estimated_weekly_follower_value
        + estimated_weekly_affiliate_revenue
        - estimated_weekly_generation_cost
    )

    notes = (
        f"週{strategy_plan.weekly_post_target}件・平均エンゲージメント{target_engagement}、"
        f"楽天アフィリエイトのクリック想定{config.ESTIMATED_WEEKLY_AFFILIATE_CLICKS}件/週を前提とした見込み値。"
        "実測の収益ではなく、config.py / .env の単価設定に基づく試算。"
    )
    if not config.RAKUTEN_AFFILIATE_ID:
        notes += " RAKUTEN_AFFILIATE_ID未設定のため、実際のリンクは収益化されていません。"

    return RevenueReport(
        id=storage.new_id("revenue"),
        generated_at=now_iso(),
        source_strategy_plan=strategy_plan.id,
        posts_published_total=posts_published_total,
        weekly_post_target=strategy_plan.weekly_post_target,
        estimated_weekly_engagement_value=round(estimated_weekly_engagement_value, 1),
        estimated_weekly_follower_value=round(estimated_weekly_follower_value, 1),
        estimated_weekly_affiliate_revenue=round(estimated_weekly_affiliate_revenue, 1),
        estimated_weekly_generation_cost=round(estimated_weekly_generation_cost, 1),
        estimated_weekly_profit=round(estimated_weekly_profit, 1),
        notes=notes,
    )


def save_revenue_report(report: RevenueReport, finance_dir=None) -> str:
    finance_dir = finance_dir or config.FINANCE_DIR
    path = finance_dir / f"{report.id}.json"
    storage.write_json(path, report.to_dict())
    return str(path)


def latest_revenue_report(finance_dir=None) -> RevenueReport | None:
    finance_dir = finance_dir or config.FINANCE_DIR
    files = storage.list_json_files(finance_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return RevenueReport.from_dict(storage.read_json(latest))


def run_finance(
    strategy_plan: StrategyPlan, history_file=None, finance_dir=None
) -> tuple[RevenueReport, str]:
    history_entries = load_publish_history(history_file)
    report = build_revenue_report(strategy_plan, history_entries)
    path = save_revenue_report(report, finance_dir)
    return report, path
