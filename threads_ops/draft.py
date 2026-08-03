"""Draft generation stage.

Turns a ResearchReport + a topic into candidate Threads post drafts, saved
as pending files for human review (see approval.py). Two generators are
available:

- TemplateDraftGenerator: fully offline, no external API. Always works.
- AnthropicDraftGenerator: uses the Claude API to write more natural
  copy, used automatically when ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import textwrap
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Protocol

from . import config, research, storage
from .models import Draft, ResearchReport, now_iso


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class DraftGenerator(Protocol):
    name: str

    def generate(self, report: ResearchReport, topic: str, count: int) -> list[str]:
        ...


class TemplateDraftGenerator:
    """Offline, deterministic draft generator based on research keywords."""

    name = "template"

    _OPENERS = [
        "{topic}について話そう。",
        "最近気づいたこと: {topic}",
        "{topic}で伸びる投稿の共通点、知ってますか?",
        "{topic}を始める前に知っておきたいこと。",
    ]

    _CLOSERS = [
        "みなさんはどう思いますか?コメントで教えてください。",
        "続きはリプ欄で。",
        "保存して後で見返してください。",
        "他にも気づいたことがあれば教えてください。",
    ]

    def generate(self, report: ResearchReport, topic: str, count: int) -> list[str]:
        keywords = [kw for kw, _ in report.top_keywords[:5]]
        hashtags = [f"#{h}" for h, _ in report.top_hashtags[:3]]
        drafts = []
        for i in range(count):
            opener = self._OPENERS[i % len(self._OPENERS)].format(topic=topic)
            closer = self._CLOSERS[i % len(self._CLOSERS)]
            body_bits = []
            if keywords:
                body_bits.append("注目ワード: " + " / ".join(keywords[:3]))
            if report.best_hours_utc:
                best_hour = report.best_hours_utc[0][0]
                body_bits.append(f"反応が良い時間帯の目安(UTC {best_hour}時)にも投稿してみましょう。")
            body = "\n".join(body_bits) if body_bits else "参考になるデータがまだ十分ではありません。"
            text = "\n\n".join([opener, body, closer])
            if hashtags:
                text += "\n\n" + " ".join(hashtags)
            drafts.append(_truncate(text, config.THREADS_MAX_CHARS))
        return drafts


class DetectiveDraftGenerator:
    """Offline generator for a detective/mystery-themed account.

    Cycles through a fixed set of content slots (morning quiz, clue, quote,
    case file, challenge to readers, daily recap) so a week of posts reads
    like a varied daily series instead of the same shape repeated.
    """

    name = "detective"

    _SLOTS = [
        (
            "【朝の推理クイズ #{n}】\n"
            "{topic}にまつわるミステリー、あなたなら解けますか?\n"
            "手がかりはコメント欄で少しずつ公開します。"
        ),
        (
            "捜査ノートより #{n}\n"
            "{topic}を調べていて気づいた小さな違和感。\n"
            "見逃さないことが真相への第一歩です。"
        ),
        (
            "探偵の心得 #{n}\n"
            "「事実は一つ、真実はいくつもある」\n"
            "{topic}を追ううえで、この言葉を忘れないようにしています。"
        ),
        (
            "事件簿ファイル #{n}\n"
            "今日扱った案件は{topic}に関するもの。\n"
            "詳しい顛末はまた明日、続きをお楽しみに。"
        ),
        (
            "読者への挑戦状 #{n}\n"
            "{topic}にまつわるこの謎、あなたなら何分で解けますか?\n"
            "答えが分かった方はコメントで教えてください。"
        ),
        (
            "今日の捜査報告 #{n}\n"
            "{topic}についての調査は一区切り。\n"
            "明日もまた新しい事件が待っています。"
        ),
    ]

    _DEFAULT_HASHTAGS = ["謎解き", "ミステリー"]

    def generate(self, report: ResearchReport, topic: str, count: int) -> list[str]:
        hashtags = list(dict.fromkeys(
            [h for h, _ in report.top_hashtags[:2]] + self._DEFAULT_HASHTAGS
        ))[:3]
        drafts = []
        for i in range(count):
            slot = self._SLOTS[i % len(self._SLOTS)]
            case_no = i // len(self._SLOTS) + 1
            text = slot.format(topic=topic, n=case_no)
            if hashtags:
                text += "\n\n" + " ".join(f"#{h}" for h in hashtags)
            drafts.append(_truncate(text, config.THREADS_MAX_CHARS))
        return drafts


class AnthropicDraftGenerator:
    """LLM-backed draft generator using the Claude API."""

    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.ANTHROPIC_API_KEY
        self.model = model or config.ANTHROPIC_MODEL

    def generate(self, report: ResearchReport, topic: str, count: int) -> list[str]:
        import anthropic  # imported lazily so the package is optional

        client = anthropic.Anthropic(api_key=self.api_key)
        keywords = ", ".join(kw for kw, _ in report.top_keywords[:8])
        hashtags = ", ".join(f"#{h}" for h, _ in report.top_hashtags[:5])
        prompt = textwrap.dedent(f"""\
            あなたはThreads(Meta)運用担当のマーケターです。
            以下の競合リサーチ結果を踏まえて、トピック「{topic}」についての
            Threads投稿文案を{count}件作成してください。

            リサーチ結果:
            - よく使われるキーワード: {keywords or "なし"}
            - よく使われるハッシュタグ: {hashtags or "なし"}
            - 平均投稿文字数: {report.avg_post_length}

            制約:
            - 1件あたり{config.THREADS_MAX_CHARS}文字以内
            - 各案は "---" だけの行で区切る
            - 前置きや説明は不要。投稿文案のみを出力する
        """)
        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        drafts = [chunk.strip() for chunk in text.split("---")]
        drafts = [d for d in drafts if d]
        return drafts[:count] if drafts else []


def get_default_generator() -> DraftGenerator:
    if config.ANTHROPIC_API_KEY:
        return AnthropicDraftGenerator()
    return TemplateDraftGenerator()


def create_drafts(
    report: ResearchReport,
    topic: str,
    count: int = 3,
    generator: DraftGenerator | None = None,
    pending_dir=None,
) -> list[Draft]:
    generator = generator or get_default_generator()
    pending_dir = pending_dir or config.PENDING_DIR

    texts = generator.generate(report, topic, count)
    drafts = []
    for text in texts:
        draft = Draft(
            id=storage.new_id("draft"),
            topic=topic,
            text=text,
            created_at=now_iso(),
            status="pending",
            source_report=report.id,
            generator=generator.name,
        )
        storage.write_json(pending_dir / f"{draft.id}.json", draft.to_dict())
        drafts.append(draft)
    return drafts


JST = timezone(timedelta(hours=9))

# 1日6投稿の既定タイムスロット(JST)。読者がアクティブになりやすい時間帯に分散させる。
DEFAULT_DAILY_TIMES = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00"]


def get_default_weekly_generator() -> DraftGenerator:
    if config.ANTHROPIC_API_KEY:
        return AnthropicDraftGenerator()
    return DetectiveDraftGenerator()


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(int(hour), int(minute))


def create_weekly_plan(
    topic: str = "探偵の事件簿",
    posts_per_day: int = 6,
    days: int = 7,
    start_date: date | None = None,
    times: list[str] | None = None,
    tz: timezone = JST,
    report: ResearchReport | None = None,
    generator: DraftGenerator | None = None,
    pending_dir=None,
) -> list[Draft]:
    """Generate a full batch of scheduled drafts (default: 7 days x 6 posts/day).

    Every draft still lands in pending/ for human review via `approval.py`;
    `scheduled_at` only controls *when* an approved draft becomes eligible
    to actually go out (see publish.publish_approved).
    """
    if posts_per_day < 1:
        raise ValueError("posts_per_day は1以上を指定してください")
    if days < 1:
        raise ValueError("days は1以上を指定してください")

    times = times or DEFAULT_DAILY_TIMES
    if len(times) < posts_per_day:
        raise ValueError("times には posts_per_day 件以上の時刻が必要です")
    slot_times = [_parse_hhmm(t) for t in times[:posts_per_day]]

    generator = generator or get_default_weekly_generator()
    pending_dir = pending_dir or config.PENDING_DIR
    report = report or research.latest_report() or research.analyze([])
    start_date = start_date or datetime.now(tz).date()

    total = days * posts_per_day
    texts = generator.generate(report, topic, total)

    drafts = []
    idx = 0
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        for slot_time in slot_times:
            scheduled_at = datetime.combine(current_date, slot_time, tzinfo=tz).isoformat()
            draft = Draft(
                id=storage.new_id("draft"),
                topic=topic,
                text=texts[idx],
                created_at=now_iso(),
                status="pending",
                source_report=report.id,
                generator=generator.name,
                scheduled_at=scheduled_at,
            )
            storage.write_json(pending_dir / f"{draft.id}.json", draft.to_dict())
            drafts.append(draft)
            idx += 1

    return drafts
