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


def test_classify_assigns_categories_and_falls_back_to_other():
    posts = [
        OwnPost(id="1", text="新サービスの募集を開始しました！", posted_at=""),
        OwnPost(id="2", text="伸びる投稿を作るコツ3選", posted_at=""),
        OwnPost(id="3", text="今日はカフェで朝ごはん", posted_at=""),
        OwnPost(id="4", text="あいうえお", posted_at=""),
    ]
    grouped = history.classify_posts(posts, history.DEFAULT_CATEGORIES)
    assert [p.id for p in grouped["告知・宣伝"]] == ["1"]
    assert [p.id for p in grouped["ノウハウ・Tips"]] == ["2"]
    assert [p.id for p in grouped["日常・雑談"]] == ["3"]
    assert [p.id for p in grouped[history.OTHER_CATEGORY]] == ["4"]
    assert posts[1].matched_keywords == ["コツ", "選"]


def test_custom_categories_file_and_save_sorted(tmp_dirs):
    storage.write_json(config.CATEGORIES_FILE, {"英語": ["english"]})
    posts = [OwnPost(id="1", text="English study", posted_at=""), OwnPost(id="2", text="無関係", posted_at="")]
    history.save_posts(posts)

    grouped = history.classify_posts(history.load_posts())
    history.save_sorted(grouped)

    sorted_dir = config.MY_POSTS_SORTED_DIR
    assert storage.read_json(sorted_dir / "英語.json")["posts"][0]["id"] == "1"
    summary = {r["category"]: r["count"] for r in storage.read_json(sorted_dir / "summary.json")["categories"]}
    assert summary == {"英語": 1, history.OTHER_CATEGORY: 1}
