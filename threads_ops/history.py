"""Own-post history stage: fetch past posts and sort them into categories.

Unlike competitor research, the official Threads API *does* expose the
authenticated account's own posts (GET /me/threads, needs the
threads_basic permission) and, optionally, per-post insights (GET
/{media-id}/insights, needs threads_manage_insights). `fetch_own_posts`
pages through all of them and saves the raw result to
data/my_posts/posts.json.

`classify_posts` then sorts each post into one category using a simple
keyword-hit count. Categories live in data/my_posts/categories.json so
they can be edited without touching code; DEFAULT_CATEGORIES is used when
that file doesn't exist. The result is written to data/my_posts/sorted/,
one JSON file per category, plus a summary.json.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import config, storage
from .models import now_iso

POST_FIELDS = "id,text,timestamp,media_type,permalink,shortcode,is_quote_post"
INSIGHT_METRICS = "views,likes,replies,reposts,quotes"
OTHER_CATEGORY = "その他"

# Checked in order; on a tie in keyword hits the earlier category wins.
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "告知・宣伝": ["告知", "お知らせ", "募集", "販売", "リリース", "公開しました", "申し込み",
                "予約", "セール", "キャンペーン", "プロフィール", "リンク", "限定"],
    "ノウハウ・Tips": ["方法", "コツ", "やり方", "ポイント", "手順", "おすすめ", "解説",
                   "まとめ", "選", "tips", "ステップ", "知っておく", "すべき", "法則"],
    "質問・問いかけ": ["?", "？", "教えて", "どう思", "みなさん", "皆さん", "アンケート",
                  "どっち", "ありますか", "ですか"],
    "実績・報告": ["達成", "突破", "フォロワー", "万円", "結果", "報告", "記録", "振り返り",
               "ありがとう", "感謝"],
    "意見・考察": ["思う", "考え", "本質", "大事", "大切", "べき", "気づ", "なぜ", "理由"],
    "日常・雑談": ["今日", "朝", "昼", "夜", "ごはん", "カフェ", "週末", "散歩", "眠", "天気",
               "休み", "旅行"],
}


@dataclass
class OwnPost:
    id: str
    text: str
    posted_at: str  # ISO-8601
    media_type: str = "TEXT_POST"
    permalink: str | None = None
    is_quote_post: bool = False
    metrics: dict[str, int] = field(default_factory=dict)
    category: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    def engagement_score(self) -> float:
        m = self.metrics
        return m.get("likes", 0) + m.get("replies", 0) * 2 + m.get("reposts", 0) * 3 + m.get("quotes", 0) * 3

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OwnPost":
        return cls(**data)

    @classmethod
    def from_api(cls, data: dict) -> "OwnPost":
        return cls(
            id=data["id"],
            text=data.get("text") or "",
            posted_at=data.get("timestamp", ""),
            media_type=data.get("media_type", "TEXT_POST"),
            permalink=data.get("permalink"),
            is_quote_post=bool(data.get("is_quote_post", False)),
        )


class ThreadsHistoryClient:
    """Read-only client for the authenticated account's own posts."""

    def __init__(self, access_token: str | None = None, session=None):
        self.access_token = access_token or config.THREADS_ACCESS_TOKEN
        if not self.access_token:
            raise RuntimeError("THREADS_ACCESS_TOKEN must be set to fetch past posts")
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def iter_posts(self, limit: int | None = None, since: str | None = None):
        params = {"fields": POST_FIELDS, "limit": 100, "access_token": self.access_token}
        if since:
            params["since"] = since
        url = f"{config.THREADS_API_BASE}/me/threads"
        fetched = 0
        while url:
            page = self._get(url, params)
            for raw in page.get("data", []):
                yield OwnPost.from_api(raw)
                fetched += 1
                if limit is not None and fetched >= limit:
                    return
            # paging.next is a full URL that already carries every query param.
            url = page.get("paging", {}).get("next")
            params = None

    def fetch_metrics(self, post_id: str) -> dict[str, int]:
        page = self._get(
            f"{config.THREADS_API_BASE}/{post_id}/insights",
            {"metric": INSIGHT_METRICS, "access_token": self.access_token},
        )
        metrics = {}
        for item in page.get("data", []):
            values = item.get("values") or [{}]
            metrics[item["name"]] = int(values[0].get("value", 0))
        return metrics


def fetch_own_posts(
    client: ThreadsHistoryClient | None = None,
    limit: int | None = None,
    since: str | None = None,
    with_insights: bool = True,
) -> tuple[list[OwnPost], list[str]]:
    """Return (posts, warnings). Insight failures don't abort the fetch."""
    client = client or ThreadsHistoryClient()
    posts = list(client.iter_posts(limit=limit, since=since))
    warnings: list[str] = []
    if with_insights:
        for post in posts:
            try:
                post.metrics = client.fetch_metrics(post.id)
            except Exception as exc:  # noqa: BLE001 - recorded and reported, fetch continues
                warnings.append(f"{post.id}: insights unavailable ({exc})")
    return posts, warnings


def save_posts(posts: list[OwnPost], path=None) -> str:
    path = path or config.MY_POSTS_FILE
    storage.write_json(path, {"fetched_at": now_iso(), "posts": [p.to_dict() for p in posts]})
    return str(path)


def load_posts(path=None) -> list[OwnPost]:
    path = path or config.MY_POSTS_FILE
    if not path.exists():
        return []
    data = storage.read_json(path)
    raw_posts = data if isinstance(data, list) else data.get("posts", [])
    return [OwnPost.from_dict(raw) for raw in raw_posts]


def load_categories(path=None) -> dict[str, list[str]]:
    path = path or config.CATEGORIES_FILE
    if path.exists():
        return storage.read_json(path)
    return DEFAULT_CATEGORIES


def classify_post(post: OwnPost, categories: dict[str, list[str]]) -> tuple[str, list[str]]:
    text = post.text.lower()
    best, best_hits = OTHER_CATEGORY, []
    for name, keywords in categories.items():
        hits = [k for k in keywords if k.lower() in text]
        if len(hits) > len(best_hits):
            best, best_hits = name, hits
    return best, best_hits


def classify_posts(posts: list[OwnPost], categories: dict[str, list[str]] | None = None) -> dict[str, list[OwnPost]]:
    categories = categories or load_categories()
    grouped: dict[str, list[OwnPost]] = {name: [] for name in [*categories, OTHER_CATEGORY]}
    for post in posts:
        post.category, post.matched_keywords = classify_post(post, categories)
        grouped[post.category].append(post)
    for group in grouped.values():
        group.sort(key=lambda p: p.engagement_score(), reverse=True)
    return grouped


def summarize(grouped: dict[str, list[OwnPost]]) -> list[dict]:
    rows = []
    for name, group in grouped.items():
        scores = [p.engagement_score() for p in group]
        rows.append({
            "category": name,
            "count": len(group),
            "avg_engagement": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "top_post": group[0].permalink or group[0].id if group else None,
        })
    return rows


def save_sorted(grouped: dict[str, list[OwnPost]], sorted_dir=None) -> str:
    sorted_dir = sorted_dir or config.MY_POSTS_SORTED_DIR
    for old in storage.list_json_files(sorted_dir):
        old.unlink()
    for name, group in grouped.items():
        if group:
            storage.write_json(sorted_dir / f"{name}.json", {"category": name, "posts": [p.to_dict() for p in group]})
    storage.write_json(sorted_dir / "summary.json", {"generated_at": now_iso(), "categories": summarize(grouped)})
    return str(sorted_dir)
