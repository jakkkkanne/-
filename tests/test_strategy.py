from threads_ops import config, draft, strategy
from threads_ops.models import MarketingPlan, ResearchReport


def _report():
    return ResearchReport(
        id="report_test",
        generated_at="2026-07-26T00:00:00+00:00",
        accounts_analyzed=["acct_a"],
        post_count=5,
        top_keywords=[["マーケティング", 3], ["顧客", 2], ["朝活", 1]],
        top_hashtags=[["マーケティング", 2], ["朝活", 1], ["習慣化", 1]],
        best_hours_utc=[[9, 120.0]],
        avg_post_length=100.0,
        top_posts=[{"likes": 100, "replies": 10, "reposts": 5}],
    )


def _marketing_plan():
    return MarketingPlan(
        id="marketing_test",
        generated_at="2026-07-26T00:00:00+00:00",
        source_report="report_test",
        target_keywords=["マーケティング"],
        hashtag_strategy=["#マーケティング"],
        best_hours_utc=[[9, 120.0]],
        tone="カジュアルで簡潔",
        posting_cadence_per_week=3,
        growth_tactics=["反応の良い時間帯に投稿する"],
    )


def test_build_strategy_plan_prioritizes_top_hashtags():
    plan = strategy.build_strategy_plan(_report(), _marketing_plan())
    assert plan.content_pillars == ["マーケティング", "朝活", "習慣化"]
    assert plan.priority_topics == ["マーケティング", "朝活", "習慣化"]
    assert plan.weekly_post_target == 3
    assert plan.source_report == "report_test"
    assert plan.source_marketing_plan == "marketing_test"
    assert plan.kpi_targets["weekly_posts"] == 3
    assert plan.kpi_targets["target_avg_engagement"] > 0


def test_build_strategy_plan_falls_back_to_keywords_when_no_hashtags():
    report = _report()
    report.top_hashtags = []
    plan = strategy.build_strategy_plan(report, _marketing_plan())
    assert plan.content_pillars == ["マーケティング", "顧客", "朝活"]


def test_build_strategy_plan_excludes_hashtags_that_are_post_type_labels():
    report = _report()
    report.top_hashtags = [["解決法", 6], ["夜泣き", 3], ["寝かしつけ", 2], ["イヤイヤ期", 1], ["沐浴", 1]]
    report.patterns_by_type = {"解決法": {"count": 6}}
    plan = strategy.build_strategy_plan(report, _marketing_plan())
    assert "解決法" not in plan.content_pillars
    assert plan.content_pillars == ["夜泣き", "寝かしつけ", "イヤイヤ期", "沐浴"]


def test_build_strategy_plan_falls_back_to_default_when_no_data():
    report = _report()
    report.top_hashtags = []
    report.top_keywords = []
    plan = strategy.build_strategy_plan(report, _marketing_plan())
    assert plan.content_pillars == ["ブランド紹介"]
    assert plan.priority_topics == ["ブランド紹介"]


def test_run_strategy_saves_and_loads_latest(tmp_dirs):
    plan, path = strategy.run_strategy(_report(), _marketing_plan(), tmp_dirs["strategy"])
    assert path.endswith(f"{plan.id}.json")

    latest = strategy.latest_strategy_plan(tmp_dirs["strategy"])
    assert latest.id == plan.id


def test_build_strategy_plan_includes_weekly_calendar():
    plan = strategy.build_strategy_plan(_report(), _marketing_plan())
    assert len(plan.weekly_calendar) == 7  # posting_cadence_per_week=3 -> 1/day
    days = {slot["day"] for slot in plan.weekly_calendar}
    assert days == {"月", "火", "水", "木", "金", "土", "日"}
    for slot in plan.weekly_calendar:
        assert slot["notes"]


def test_build_weekly_calendar_uses_day_hour_performance_when_available():
    report = _report()
    report.day_hour_performance = [["月", 21, 500.0, 3], ["火", 9, 300.0, 2]]
    plan = _marketing_plan()
    plan.predicted_trending_type = "解決法"
    plan.target_resonant_type = "困りごと"

    calendar = strategy.build_weekly_calendar(report, plan, ["夜泣き"], posts_per_day=1)
    monday_slot = next(s for s in calendar if s["day"] == "月")
    assert monday_slot["hour"] == 21
    assert "実績枠" in monday_slot["notes"]


def test_build_weekly_calendar_shows_product_name_not_url_within_price_band():
    report = _report()
    plan = _marketing_plan()
    plan.predicted_trending_type = "解決法"

    calendar = strategy.build_weekly_calendar(
        report, plan, ["夜泣き"], posts_per_day=1, min_price_jpy=2000, max_price_jpy=6000
    )
    slot = calendar[0]
    assert slot["product_name"] == "ホワイトノイズマシン"
    assert "http" not in slot["notes"]
    assert "http" not in (slot["product_name"] or "")


def test_build_weekly_calendar_excludes_product_outside_price_band():
    report = _report()
    plan = _marketing_plan()
    plan.predicted_trending_type = "解決法"

    calendar = strategy.build_weekly_calendar(
        report, plan, ["イヤイヤ期"], posts_per_day=1, min_price_jpy=2000, max_price_jpy=6000
    )
    slot = calendar[0]
    assert slot["product_name"] is None
    assert "見送り" in slot["notes"]


def _product_with_insight():
    return {
        "pain_point": "夜泣き",
        "name": "ホワイトノイズマシン",
        "price_jpy": 3480,
        "review_count": 4200,
        "review_insight": {
            "pain": "抱っこしても寝てもすぐ起きて夜中に何度も起こされる",
            "resolution": "ホワイトノイズを流すようにしたら寝つきと寝続ける時間が伸びた",
        },
    }


def test_build_product_thread_has_three_segments_in_order():
    segments = strategy.build_product_thread(_product_with_insight())
    assert len(segments) == 3
    hook, testimonial, solution = segments
    assert "抱っこしても寝てもすぐ起きて夜中に何度も起こされる" in hook
    assert "ホワイトノイズを流すようにしたら寝つきと寝続ける時間が伸びた" in solution
    assert "[ホワイトノイズマシン]" in solution


def test_build_product_thread_excludes_url_and_stays_within_char_budget():
    segments = strategy.build_product_thread(_product_with_insight())
    for segment in segments:
        assert "http" not in segment
        assert draft.visible_length(segment) <= config.THREADS_MAX_CHARS


def test_build_product_thread_no_insight_returns_empty():
    product = {"name": "テスト商品", "review_insight": {"pain": None, "resolution": None}}
    assert strategy.build_product_thread(product) == []


def test_build_product_threads_groups_by_genre_and_skips_missing_insight():
    products = [
        _product_with_insight(),
        {"pain_point": "沐浴", "name": "沐浴チェア", "price_jpy": 2980, "review_insight": {}},
    ]
    threads = strategy.build_product_threads(products)
    assert len(threads) == 1  # the second product has no usable insight
    assert threads[0]["genre"] == "夜泣き"
    assert threads[0]["product_name"] == "ホワイトノイズマシン"
    assert len(threads[0]["segments"]) == 3


def test_build_araru_resolution_thread_has_two_segments_in_order():
    segments = strategy.build_araru_resolution_thread(_product_with_insight())
    assert len(segments) == 2
    araru, solution = segments
    assert "抱っこしても寝てもすぐ起きて夜中に何度も起こされる" in araru
    assert "ホワイトノイズを流すようにしたら寝つきと寝続ける時間が伸びた" in solution
    assert "[ホワイトノイズマシン]" in solution


def test_build_araru_resolution_thread_excludes_url_and_stays_within_char_budget():
    segments = strategy.build_araru_resolution_thread(_product_with_insight())
    for segment in segments:
        assert "http" not in segment
        assert draft.visible_length(segment) <= config.THREADS_MAX_CHARS


def test_build_araru_resolution_thread_no_insight_returns_empty():
    product = {"name": "テスト商品", "review_insight": {"pain": None, "resolution": None}}
    assert strategy.build_araru_resolution_thread(product) == []


def test_build_araru_resolution_threads_groups_by_genre_and_skips_missing_insight():
    products = [
        _product_with_insight(),
        {"pain_point": "沐浴", "name": "沐浴チェア", "price_jpy": 2980, "review_insight": {}},
    ]
    threads = strategy.build_araru_resolution_threads(products)
    assert len(threads) == 1  # the second product has no usable insight
    assert threads[0]["genre"] == "夜泣き"
    assert threads[0]["product_name"] == "ホワイトノイズマシン"
    assert len(threads[0]["segments"]) == 2
