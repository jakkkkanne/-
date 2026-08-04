from threads_ops import marketing
from threads_ops.models import ResearchReport


def _report(post_count=5, avg_len=100.0):
    return ResearchReport(
        id="report_test",
        generated_at="2026-07-26T00:00:00+00:00",
        accounts_analyzed=["acct_a"],
        post_count=post_count,
        top_keywords=[["マーケティング", 3], ["顧客", 2]],
        top_hashtags=[["マーケティング", 2], ["sns運用", 1]],
        best_hours_utc=[[9, 120.0]],
        avg_post_length=avg_len,
        top_posts=[],
    )


def test_build_marketing_plan_casual_tone_for_short_posts():
    plan = marketing.build_marketing_plan(_report(avg_len=80.0))
    assert plan.tone == "カジュアルで簡潔"
    assert plan.source_report == "report_test"
    assert plan.hashtag_strategy == ["#マーケティング", "#sns運用"]
    assert plan.posting_cadence_per_week == 3


def test_build_marketing_plan_high_volume_gets_daily_cadence():
    plan = marketing.build_marketing_plan(_report(post_count=25))
    assert plan.posting_cadence_per_week == 7
    assert len(plan.growth_tactics) == 4


def test_build_marketing_plan_no_posts_gets_minimum_cadence():
    plan = marketing.build_marketing_plan(_report(post_count=0))
    assert plan.posting_cadence_per_week == 1


def test_build_marketing_plan_respects_weekly_target_override(monkeypatch):
    from threads_ops import config

    monkeypatch.setattr(config, "WEEKLY_POST_TARGET_OVERRIDE", 42)
    plan = marketing.build_marketing_plan(_report(post_count=5))
    assert plan.posting_cadence_per_week == 42


def test_run_marketing_saves_and_loads_latest(tmp_dirs):
    report = _report()
    plan, path = marketing.run_marketing(report, tmp_dirs["marketing"])
    assert path.endswith(f"{plan.id}.json")

    latest = marketing.latest_marketing_plan(tmp_dirs["marketing"])
    assert latest.id == plan.id


def test_latest_marketing_plan_returns_none_when_empty(tmp_dirs):
    assert marketing.latest_marketing_plan(tmp_dirs["marketing"]) is None
