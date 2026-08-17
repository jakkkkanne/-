from threads_ops import config, draft
from threads_ops.models import MarketingPlan, ResearchReport


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


def _marketing_plan(tone="詳しく丁寧"):
    return MarketingPlan(
        id="marketing_test",
        generated_at="2026-07-26T00:00:00+00:00",
        source_report="report_test",
        target_keywords=["マーケティング"],
        hashtag_strategy=["#マーケティング", "#sns運用"],
        best_hours_utc=[[9, 120.0]],
        tone=tone,
        posting_cadence_per_week=3,
        growth_tactics=["リプライ欄で会話を続ける", "保存されやすいリスト形式にする"],
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


def test_template_generator_uses_polite_tone_from_marketing_plan():
    generator = draft.TemplateDraftGenerator()
    drafts = generator.generate(_report(), topic="朝活", count=2, marketing_plan=_marketing_plan("詳しく丁寧"))

    for text in drafts:
        assert "ご紹介" in text or "ぜひ" in text or "皆様" in text or "ご案内" in text


def test_template_generator_stays_casual_without_polite_tone():
    generator = draft.TemplateDraftGenerator()
    drafts = generator.generate(_report(), topic="朝活", count=2, marketing_plan=_marketing_plan("カジュアルで簡潔"))

    for text in drafts:
        assert "皆様" not in text


def test_template_generator_includes_growth_tactic_when_marketing_plan_given():
    generator = draft.TemplateDraftGenerator()
    plan = _marketing_plan()
    drafts = generator.generate(_report(), topic="朝活", count=1, marketing_plan=plan)

    assert "施策: " + plan.growth_tactics[0] in drafts[0]


def test_template_generator_does_not_include_hashtags():
    generator = draft.TemplateDraftGenerator()
    plan = _marketing_plan()
    drafts = generator.generate(_report(), topic="朝活", count=3, marketing_plan=plan)

    for text in drafts:
        assert "#" not in text


def test_create_drafts_passes_marketing_plan_through(tmp_dirs):
    report = _report()
    plan = _marketing_plan()
    drafts = draft.create_drafts(
        report,
        topic="朝活",
        count=1,
        generator=draft.TemplateDraftGenerator(),
        pending_dir=tmp_dirs["pending"],
        marketing_plan=plan,
    )
    assert "施策: " + plan.growth_tactics[0] in drafts[0].text
