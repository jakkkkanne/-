from threads_ops import config, history, storage
from threads_ops.history import OwnPost


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class _FakeSession:
    """Serves two pages of posts and insights for each post id."""

    def __init__(self, fail_insights=False):
        self.fail_insights = fail_insights
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if url.endswith("/insights"):
            if self.fail_insights:
                raise RuntimeError("403")
            return _FakeResponse({"data": [
                {"name": "likes", "values": [{"value": 10}]},
                {"name": "replies", "values": [{"value": 2}]},
            ]})
        if url == "NEXT_PAGE":
            return _FakeResponse({"data": [
                {"id": "3", "text": "今日はカフェで朝ごはん", "timestamp": "2026-07-03T00:00:00+0000"},
            ]})
        return _FakeResponse({
            "data": [
                {"id": "1", "text": "新サービスの募集を開始しました！", "timestamp": "2026-07-01T00:00:00+0000",
                 "media_type": "TEXT_POST", "permalink": "https://threads.net/p/1"},
                {"id": "2", "text": "伸びる投稿を作るコツ3選", "timestamp": "2026-07-02T00:00:00+0000"},
            ],
            "paging": {"next": "NEXT_PAGE"},
        })


def _client(**kwargs):
    return history.ThreadsHistoryClient(access_token="tok", session=_FakeSession(**kwargs))


def test_fetch_follows_paging_and_collects_insights():
    posts, warnings = history.fetch_own_posts(client=_client())
    assert [p.id for p in posts] == ["1", "2", "3"]
    assert posts[0].metrics == {"likes": 10, "replies": 2}
    assert posts[0].permalink == "https://threads.net/p/1"
    assert warnings == []


def test_fetch_respects_limit_and_skips_insights():
    client = _client()
    posts, _ = history.fetch_own_posts(client=client, limit=2, with_insights=False)
    assert len(posts) == 2
    assert not any(url.endswith("/insights") for url, _ in client.session.calls)


def test_insight_failures_are_warnings_not_errors():
    posts, warnings = history.fetch_own_posts(client=_client(fail_insights=True))
    assert len(posts) == 3
    assert len(warnings) == 3


def test_triage_keeps_theme_posts_and_flags_unrelated_or_private():
    posts = [
        OwnPost(id="keep", text="2歳のイヤイヤ期、朝の着替えが戦場。前の晩に1日分ずつ袋にまとめたらラクになった",
                posted_at="", metrics={"likes": 5}),
        OwnPost(id="revise", text="最近買ったグッズの話", posted_at=""),
        OwnPost(id="unrelated", text="今日のランチはラーメン", posted_at=""),
        OwnPost(id="private", text="娘のさくら第一保育園の運動会、子どもたち頑張ってた", posted_at=""),
        OwnPost(id="phone", text="育児相談はこちら 090-1234-5678 子育て", posted_at=""),
    ]
    grouped = history.classify_posts(posts)
    assert [p.id for p in grouped[history.KEEP]] == ["keep"]
    assert [p.id for p in grouped[history.REVISE]] == ["revise"]
    assert {p.id for p in grouped[history.DELETE]} == {"unrelated", "private", "phone"}
    assert "園・学校の名前" in posts[3].reasons[0]
    assert "電話番号" in posts[4].reasons[0]


def test_generic_school_mentions_are_not_privacy_flags():
    post = OwnPost(id="1", text="娘が来年小学校。入学準備のグッズを揃え中", posted_at="")
    history.classify_posts([post])
    assert post.verdict == history.KEEP


def test_posts_get_a_content_pillar():
    posts = [
        OwnPost(id="1", text="離乳食で買ってよかったグッズ、正直レビュー", posted_at=""),
        OwnPost(id="2", text="100均のジップ袋と家にある物でできる時短アイデア", posted_at=""),
        OwnPost(id="3", text="寝かしつけで困ってたけど、ライトで解決してラクになった", posted_at=""),
        OwnPost(id="4", text="みんなは保育園の準備どうしてる？", posted_at=""),
    ]
    history.classify_posts(posts)
    assert [p.category for p in posts] == ["買ってよかった", "0円アイデア", "困り事→解決", "質問・アンケート"]


def test_custom_rules_file_and_save_sorted(tmp_dirs):
    storage.write_json(config.CLASSIFY_RULES_FILE, {"theme_keywords": ["english", "study"]})
    posts = [OwnPost(id="1", text="English study", posted_at=""), OwnPost(id="2", text="無関係", posted_at="")]
    history.save_posts(posts)

    grouped = history.classify_posts(history.load_posts())
    history.save_sorted(grouped)

    sorted_dir = config.MY_POSTS_SORTED_DIR
    assert storage.read_json(sorted_dir / f"{history.KEEP}.json")["posts"][0]["id"] == "1"
    summary = {r["verdict"]: r["count"] for r in storage.read_json(sorted_dir / "summary.json")["verdicts"]}
    assert summary == {history.KEEP: 1, history.REVISE: 0, history.DELETE: 1}
    checklist = (sorted_dir / "棚卸し.md").read_text(encoding="utf-8")
    assert "- [ ]" in checklist and "English study" in checklist
