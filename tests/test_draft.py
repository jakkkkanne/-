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
