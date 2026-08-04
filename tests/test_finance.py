from threads_ops import config, finance, storage
from threads_ops.models import StrategyPlan


def _strategy_plan(weekly_post_target=3, target_avg_engagement=100.0, target_follower_growth_pct=5.0):
    return StrategyPlan(
        id="strategy_test",
        generated_at="2026-07-26T00:00:00+00:00",
        source_report="report_test",
        source_marketing_plan="marketing_test",
        content_pillars=["マーケティング"],
        priority_topics=["マーケティング"],
        weekly_post_target=weekly_post_target,
        kpi_targets={
            "weekly_posts": weekly_post_target,
            "target_avg_engagement": target_avg_engagement,
            "target_follower_growth_pct": target_follower_growth_pct,
        },
        notes="",
    )


def test_build_revenue_report_computes_projection(monkeypatch):
    monkeypatch.setattr(config, "REVENUE_PER_ENGAGEMENT_POINT", 3.0)
    monkeypatch.setattr(config, "REVENUE_PER_NEW_FOLLOWER", 20.0)
    monkeypatch.setattr(config, "CURRENT_FOLLOWER_COUNT", 1000)
    monkeypatch.setattr(config, "COST_PER_DRAFT_GENERATED", 1.0)

    plan = _strategy_plan(weekly_post_target=3, target_avg_engagement=100.0, target_follower_growth_pct=5.0)
    report = finance.build_revenue_report(plan, history_entries=[])

    assert report.source_strategy_plan == "strategy_test"
    assert report.weekly_post_target == 3
    assert report.estimated_weekly_engagement_value == 900.0  # 3 * 100 * 3.0
    assert report.estimated_weekly_follower_value == 1000.0  # 1000 * 0.05 * 20.0
    assert report.estimated_weekly_generation_cost == 3.0  # 3 * 1.0
    assert report.estimated_weekly_profit == 1897.0


def test_build_revenue_report_counts_only_successful_publishes():
    history = [
        {"success": True},
        {"success": True},
        {"success": False},
    ]
    report = finance.build_revenue_report(_strategy_plan(), history_entries=history)
    assert report.posts_published_total == 2


def test_run_finance_saves_and_loads_latest(tmp_dirs):
    history_file = tmp_dirs["history"]
    storage.append_jsonl(history_file, {"success": True})

    report, path = finance.run_finance(_strategy_plan(), history_file=history_file, finance_dir=tmp_dirs["finance"])
    assert path.endswith(f"{report.id}.json")
    assert report.posts_published_total == 1

    latest = finance.latest_revenue_report(tmp_dirs["finance"])
    assert latest.id == report.id


def test_load_publish_history_returns_empty_list_when_missing(tmp_dirs):
    assert finance.load_publish_history(tmp_dirs["history"]) == []


def test_latest_revenue_report_returns_none_when_empty(tmp_dirs):
    assert finance.latest_revenue_report(tmp_dirs["finance"]) is None
