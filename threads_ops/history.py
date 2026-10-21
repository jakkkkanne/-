"""Own-post history stage: fetch past posts and sort them into categories.

Unlike competitor research, the official Threads API *does* expose the
authenticated account's own posts (GET /me/threads, needs the
threads_basic permission) and, optionally, per-post insights (GET
/{media-id}/insights, needs threads_manage_insights). `fetch_own_posts`
pages through all of them and saves the raw result to
data/my_posts/posts.json.

`classify_posts` then triages each post against the account concept
(育児の"困った"を、モノとアイデアで5分ラクにする) into 残す / 手直し /
削除候補, with the reasons, and also labels it with one content pillar
(困り事→解決, 0円アイデア, ...). Nothing is ever deleted automatically: the
result is a review sheet for a human. Keywords live in
data/my_posts/classify_rules.json ({"theme_keywords": [...], "categories":
{...}}, both optional) so they can be edited without touching code.
Results go to data/my_posts/sorted/: one JSON file per verdict,
summary.json, and a Markdown checklist (棚卸し.md).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import config, storage
from .models import now_iso

POST_FIELDS = "id,text,timestamp,media_type,permalink,shortcode,is_quote_post"
INSIGHT_METRICS = "views,likes,replies,reposts,quotes"
OTHER_CATEGORY = "その他"

KEEP, REVISE, DELETE = "残す", "手直し", "削除候補"
VERDICTS = (KEEP, REVISE, DELETE)

# Words that tie a post to the account theme (育児の困り事 × グッズ・時短・アイデア).
DEFAULT_THEME_KEYWORDS = [
    "育児", "子育て", "子ども", "子供", "こども", "息子", "娘", "2歳", "6歳", "イヤイヤ",
    "保育園", "幼稚園", "小学校", "入学", "ランドセル", "寝かしつけ", "夜泣き", "オムツ",
    "おむつ", "離乳食", "着替え", "お風呂", "パパ", "ママ", "ワンオペ", "時短", "グッズ",
    "100均", "買ってよかった", "便利", "ラクに", "楽に", "工夫", "困った", "困り",
]

# Content pillars from .company/secretary/notes/threads-concept.md.
# Checked in order; on a tie in keyword hits the earlier category wins.
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "買ってよかった": ["買ってよかった", "買って良かった", "レビュー", "愛用", "グッズ", "商品",
                 "使ってみた", "おすすめ", "PR", "楽天", "Amazon"],
    "0円アイデア": ["100均", "家にある", "0円", "アイデア", "工夫", "裏ワザ", "ワザ", "やり方",
                "コツ", "前の晩"],
    "困り事→解決": ["困って", "困った", "困り", "解決", "ラクに", "楽に", "助かった", "ストレス",
                "戦場", "大変"],
    "質問・アンケート": ["?", "？", "教えて", "みんなは", "みなさん", "皆さん", "どうしてる",
                   "アンケート", "どっち"],
}

# Things that look like personal information. Matches are only flagged for
# a human to check -- the patterns are deliberately broad.
PRIVACY_PATTERNS = {
    "電話番号": re.compile(r"0\d{1,4}-\d{1,4}-\d{3,4}|0[789]0\d{8}"),
    "メールアドレス": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "郵便番号": re.compile(r"〒\s?\d{3}-?\d{4}"),
    "住所(丁目・番地)": re.compile(r"\d+\s?(丁目|番地)"),
    "園・学校の名前": re.compile(r"(?<![一-龥ァ-ヶ])([一-龥ァ-ヶ]{2,})(保育園|幼稚園|こども園|小学校)"),
}
# Common words that precede 保育園/小学校 without naming a specific one.
_GENERIC_SCHOOL_PREFIXES = ("来年", "今年", "去年", "毎日", "今日", "明日", "昨日", "近所", "地元", "公立", "私立")


def _privacy_flags(text: str) -> list[str]:
    flags = []
    for label, pattern in PRIVACY_PATTERNS.items():
        for match in pattern.finditer(text):
            if label == "園・学校の名前" and match.group(1).endswith(_GENERIC_SCHOOL_PREFIXES):
                continue
            flags.append(label)
            break
    return flags


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
    verdict: str | None = None
    reasons: list[str] = field(default_factory=list)

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


def load_rules(path=None) -> tuple[list[str], dict[str, list[str]]]:
    path = path or config.CLASSIFY_RULES_FILE
    rules = storage.read_json(path) if path.exists() else {}
    return rules.get("theme_keywords", DEFAULT_THEME_KEYWORDS), rules.get("categories", DEFAULT_CATEGORIES)


def _hits(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [k for k in keywords if k.lower() in lowered]


def classify_post(post: OwnPost, categories: dict[str, list[str]]) -> tuple[str, list[str]]:
    best, best_hits = OTHER_CATEGORY, []
    for name, keywords in categories.items():
        hits = _hits(post.text, keywords)
        if len(hits) > len(best_hits):
            best, best_hits = name, hits
    return best, best_hits


def triage_post(post: OwnPost, theme_keywords: list[str]) -> tuple[str, list[str]]:
    privacy = _privacy_flags(post.text)
    if privacy:
        return DELETE, [f"個人情報の可能性: {', '.join(privacy)}"]
    theme_hits = _hits(post.text, theme_keywords)
    if len(theme_hits) >= 2:
        return KEEP, [f"テーマに合致: {', '.join(theme_hits)}"]
    if theme_hits:
        return REVISE, [f"テーマとのつながりが弱い({theme_hits[0]} のみ)。困り事と解決策をはっきり書く"]
    return DELETE, ["テーマ(育児の困り事 × グッズ・時短)との関係が見当たらない"]


def classify_posts(
    posts: list[OwnPost],
    categories: dict[str, list[str]] | None = None,
    theme_keywords: list[str] | None = None,
) -> dict[str, list[OwnPost]]:
    """Triage posts into 残す / 手直し / 削除候補 and label each with a pillar."""
    default_theme, default_categories = load_rules()
    categories = categories or default_categories
    theme_keywords = theme_keywords or default_theme
    grouped: dict[str, list[OwnPost]] = {v: [] for v in VERDICTS}
    for post in posts:
        post.category, post.matched_keywords = classify_post(post, categories)
        post.verdict, post.reasons = triage_post(post, theme_keywords)
        grouped[post.verdict].append(post)
    for group in grouped.values():
        group.sort(key=lambda p: p.engagement_score(), reverse=True)
    return grouped


def summarize(grouped: dict[str, list[OwnPost]]) -> dict:
    verdicts = []
    pillars: dict[str, int] = {}
    for name, group in grouped.items():
        scores = [p.engagement_score() for p in group]
        verdicts.append({
            "verdict": name,
            "count": len(group),
            "avg_engagement": round(sum(scores) / len(scores), 1) if scores else 0.0,
        })
        for post in group:
            pillars[post.category] = pillars.get(post.category, 0) + 1
    return {"verdicts": verdicts, "pillars": pillars}


def render_checklist(grouped: dict[str, list[OwnPost]]) -> str:
    lines = ["# 過去投稿の棚卸し", "", f"生成: {now_iso()}", "",
             "自動判定は目安です。各投稿を開いて確認し、チェックを付けてから対応してください。", ""]
    for name, group in grouped.items():
        lines += [f"## {name}({len(group)}件)", ""]
        for post in group:
            excerpt = post.text.replace("\n", " ")[:60]
            link = post.permalink or post.id
            lines.append(f"- [ ] {post.posted_at[:10]} [{post.category}] {excerpt}")
            lines.append(f"  - 理由: {' / '.join(post.reasons)} | スコア: {post.engagement_score():g} | {link}")
        lines.append("")
    return "\n".join(lines)


def save_sorted(grouped: dict[str, list[OwnPost]], sorted_dir=None) -> str:
    sorted_dir = sorted_dir or config.MY_POSTS_SORTED_DIR
    for old in storage.list_json_files(sorted_dir):
        old.unlink()
    for name, group in grouped.items():
        if group:
            storage.write_json(sorted_dir / f"{name}.json", {"verdict": name, "posts": [p.to_dict() for p in group]})
    storage.write_json(sorted_dir / "summary.json", {"generated_at": now_iso(), **summarize(grouped)})
    (sorted_dir / "棚卸し.md").write_text(render_checklist(grouped), encoding="utf-8")
    return str(sorted_dir)
