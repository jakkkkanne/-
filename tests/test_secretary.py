from threads_ops import secretary, storage
from threads_ops.models import CompetitorPost


def _write_competitor_data(tmp_dirs):
    posts = [
        CompetitorPost(
            account="acct_a",
            text="顧客理解が大事 マーケティング 基本のキ",
            posted_at="2026-07-20T09:00:00+00:00",
            likes=100,
            replies=10,
            reposts=5,
            hashtags=["マーケティング"],
        ),
        CompetitorPost(
            account="acct_b",
            text="リライトが最強 マーケティング 手法 #SNS運用",
            posted_at="2026-07-20T09:30:00+00:00",
            likes=50,
            replies=5,
            reposts=1,
        ),
    ]
    storage.write_json(
        tmp_dirs["competitors"] / "acct.json",
        {"posts": [p.to_dict() for p in posts]},
    )


def test_run_company_cycle_produces_report_and_drafts(tmp_dirs):
    _write_competitor_data(tmp_dirs)

    report, path = secretary.run_company_cycle(topic_count=2, drafts_per_topic=1)

    assert path.endswith(f"{report.id}.json")
    assert set(report.department_summaries) == {"research", "marketing", "strategy", "secretary"}
    assert len(report.draft_ids) == 2  # 2 topics x 1 draft each
    assert report.next_actions

    pending_files = list(tmp_dirs["pending"].glob("*.json"))
    assert len(pending_files) == 2


def test_run_company_cycle_with_no_competitor_data_still_drafts(tmp_dirs):
    report, _ = secretary.run_company_cycle(topic_count=1, drafts_per_topic=1)

    assert len(report.draft_ids) == 1
    pending_files = list(tmp_dirs["pending"].glob("*.json"))
    assert len(pending_files) == 1


def test_latest_company_report_returns_none_when_empty(tmp_dirs):
    assert secretary.latest_company_report(tmp_dirs["secretary"]) is None
