from threads_ops import research, storage
from threads_ops.models import CompetitorPost


def _sample_posts():
    return [
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


def test_analyze_empty_returns_zeroed_report():
    report = research.analyze([])
    assert report.post_count == 0
    assert report.top_keywords == []
    assert report.avg_post_length == 0.0


def test_analyze_counts_keywords_hashtags_and_engagement():
    report = research.analyze(_sample_posts())

    assert report.post_count == 2
    assert report.accounts_analyzed == ["acct_a", "acct_b"]

    keywords = dict(report.top_keywords)
    assert keywords.get("マーケティング") == 2

    hashtags = dict(report.top_hashtags)
    assert hashtags.get("マーケティング") == 1
    assert hashtags.get("sns運用") == 1

    assert len(report.best_hours_utc) == 1
    hour, avg_engagement = report.best_hours_utc[0]
    assert hour == 9
    assert avg_engagement > 0

    assert report.top_posts[0]["account"] == "acct_a"  # higher engagement score


def test_load_competitor_posts_reads_json_files(tmp_dirs):
    storage.write_json(
        tmp_dirs["competitors"] / "acct.json",
        {"posts": [p.to_dict() for p in _sample_posts()]},
    )
    posts = research.load_competitor_posts(tmp_dirs["competitors"])
    assert len(posts) == 2


def test_run_research_saves_report(tmp_dirs):
    storage.write_json(
        tmp_dirs["competitors"] / "acct.json",
        {"posts": [p.to_dict() for p in _sample_posts()]},
    )
    report, path = research.run_research(tmp_dirs["competitors"], tmp_dirs["reports"])
    assert report.post_count == 2

    latest = research.latest_report(tmp_dirs["reports"])
    assert latest.id == report.id
