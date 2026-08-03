from datetime import date

from threads_ops import config, draft
from threads_ops.models import ResearchReport


def _report():
    return ResearchReport(
        id="report_test",
        generated_at="2026-07-26T00:00:00+00:00",
        accounts_analyzed=["acct_a"],
        post_count=3,
        top_keywords=[["マーケティング", 3], ["顧客", 2]],
        top_hashtags=[["マーケティング", 2]],
        best_hours_utc=[[9, 120.0]],
        avg_post_length=80.0,
        top_posts=[],
    )


def test_template_generator_produces_requested_count_within_char_limit():
    generator = draft.TemplateDraftGenerator()
    drafts = generator.generate(_report(), topic="朝活", count=3)

    assert len(drafts) == 3
    for text in drafts:
        assert len(text) <= config.THREADS_MAX_CHARS
        assert "朝活" in text


def test_create_drafts_saves_pending_files(tmp_dirs):
    report = _report()
    drafts = draft.create_drafts(
        report, topic="朝活", count=2, generator=draft.TemplateDraftGenerator(), pending_dir=tmp_dirs["pending"]
    )

    assert len(drafts) == 2
    saved = list(tmp_dirs["pending"].glob("*.json"))
    assert len(saved) == 2
    for d in drafts:
        assert d.status == "pending"
        assert d.source_report == report.id


def test_detective_generator_produces_requested_count_within_char_limit():
    generator = draft.DetectiveDraftGenerator()
    drafts = generator.generate(_report(), topic="ignored", count=12)

    assert len(drafts) == 12
    for text in drafts:
        assert len(text) <= config.THREADS_MAX_CHARS
        assert "#浮気調査" in text and "#探偵" in text

    # Two full cases (6 slots each): each case tells the story in the same
    # fixed order, so post 0 and post 6 are both "client intro" beats.
    assert "依頼人紹介" in drafts[0]
    assert "依頼人紹介" in drafts[6]
    assert "調査報告" in drafts[5]


def test_create_weekly_plan_generates_six_per_day_for_a_week(tmp_dirs):
    drafts = draft.create_weekly_plan(
        posts_per_day=6,
        days=7,
        start_date=date(2026, 8, 3),
        generator=draft.DetectiveDraftGenerator(),
        pending_dir=tmp_dirs["pending"],
    )

    assert len(drafts) == 42
    saved = list(tmp_dirs["pending"].glob("*.json"))
    assert len(saved) == 42
    for d in drafts:
        assert d.status == "pending"
        assert d.scheduled_at is not None

    # 6 posts/day spread across 7 consecutive days, each at the same times.
    days_seen = {d.scheduled_at[:10] for d in drafts}
    assert days_seen == {f"2026-08-{day:02d}" for day in range(3, 10)}
    first_day_times = sorted(d.scheduled_at[11:16] for d in drafts if d.scheduled_at.startswith("2026-08-03"))
    assert first_day_times == draft.DEFAULT_DAILY_TIMES


def test_create_weekly_plan_rejects_too_few_times(tmp_dirs):
    try:
        draft.create_weekly_plan(
            posts_per_day=6,
            days=1,
            times=["07:00"],
            generator=draft.DetectiveDraftGenerator(),
            pending_dir=tmp_dirs["pending"],
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
