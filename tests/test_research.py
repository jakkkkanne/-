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
    assert report.viral_post_count == 0
    assert report.patterns_by_type == {}


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


def _viral_posts():
    return [
        CompetitorPost(
            account="acct_a",
            text="子育てあるある、わかる人だけ集まれ",
            posted_at="2026-07-20T09:00:00+00:00",
            likes=1000,
            replies=100,
            reposts=50,
            views=15000,
            post_type="あるある",
        ),
        CompetitorPost(
            account="acct_a",
            text="夜泣きで困っていませんか?",
            posted_at="2026-07-20T09:10:00+00:00",
            likes=800,
            replies=90,
            reposts=40,
            views=12000,
            post_type="困りごと",
        ),
        CompetitorPost(
            account="acct_b",
            text="閲覧数が少ない普通の投稿",
            posted_at="2026-07-20T09:20:00+00:00",
            likes=10,
            replies=1,
            reposts=0,
            views=500,
        ),
    ]


def test_analyze_identifies_viral_posts_and_patterns_by_type(monkeypatch):
    from threads_ops import config

    monkeypatch.setattr(config, "MIN_VIRAL_VIEWS", 10000)
    report = research.analyze(_viral_posts())

    assert report.viral_post_count == 2
    assert report.viral_avg_views == 13500.0
    assert set(report.patterns_by_type) == {"あるある", "困りごと"}
    assert report.patterns_by_type["あるある"]["count"] == 1
    assert report.patterns_by_type["あるある"]["avg_views"] == 15000.0
    assert report.patterns_by_type["あるある"]["avg_replies"] == 100.0
    assert report.patterns_by_type["あるある"]["sample_openers"]


def test_day_hour_performance_scoped_to_text_only_posts(monkeypatch):
    from threads_ops import config

    monkeypatch.setattr(config, "MIN_VIRAL_VIEWS", 10000)
    posts = _viral_posts() + [
        CompetitorPost(
            account="acct_c",
            text="画像つきなので集計対象外",
            posted_at="2026-07-20T09:00:00+00:00",
            likes=5000,
            replies=500,
            reposts=200,
            views=50000,
            post_type="解決法",
            media_type="image",
        ),
    ]
    report = research.analyze(posts)

    # 2026-07-20 is a Monday; only the two text-only posts count.
    assert report.text_only_post_count == 3
    assert report.day_hour_performance
    weekday, hour, avg_score, count = report.day_hour_performance[0]
    assert weekday == "月"
    assert hour == 9
    assert count == 3

    # The image post is excluded from the text-only viral pattern analysis.
    assert "解決法" not in report.text_only_patterns_by_type
    assert set(report.text_only_patterns_by_type) == {"あるある", "困りごと"}
