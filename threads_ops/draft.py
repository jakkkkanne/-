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
    """Offline generator for the account's fixed genre: a private detective
    recounting cases where a man in his 30s, cheated on by his wife, hired
    the agency to investigate.

    Every `len(_SLOTS)` posts form one case, told in order across a single
    day (client intro -> consultation -> investigation plan -> stakeout ->
    evidence -> outcome), so with the default 6 posts/day each day reads as
    a new case in the same recurring format. `topic` is accepted for
    Protocol/API compatibility and stored as Draft metadata, but the story
    itself is fixed -- that's the point of "unifying" the genre.
    """

    name = "detective"

    _CLIENT_AGES = [32, 34, 36, 38, 33, 37, 39]

    _SLOTS = [
        (
            "【依頼人紹介 #{n}】\n"
            "今回の依頼人は{age}歳、会社員の男性。\n"
            "「妻の様子が最近おかしい」と、当探偵事務所を訪ねてこられました。"
        ),
        (
            "相談内容 #{n}\n"
            "「スマホを肌身離さず持つようになった」「休日の外出が増えた」。\n"
            "小さな違和感の積み重ねが、依頼のきっかけでした。"
        ),
        (
            "調査方針 #{n}\n"
            "依頼人と相談のうえ、まずは奥さまの行動パターンを記録することに。\n"
            "尾行・張り込みの準備を進めます。"
        ),
        (
            "調査開始 #{n}\n"
            "指定した日、奥さまの後を追います。\n"
            "向かった先は、いつもと違う駅前のカフェでした。"
        ),
        (
            "証拠の記録 #{n}\n"
            "奥さまが見知らぬ男性と合流する瞬間を記録。\n"
            "日時・場所を添えた写真は、揺るぎない証拠になります。"
        ),
        (
            "調査報告 #{n}\n"
            "証拠一式を依頼人にお渡ししました。\n"
            "そこから先を決めるのは依頼人自身ですが、事実を知る権利は誰にでもあります。"
        ),
    ]

    _DEFAULT_HASHTAGS = ["浮気調査", "探偵"]

    def generate(self, report: ResearchReport, topic: str, count: int) -> list[str]:
        hashtags = list(dict.fromkeys(
            [h for h, _ in report.top_hashtags[:1]] + self._DEFAULT_HASHTAGS
        ))[:3]
        drafts = []
        for i in range(count):
            slot = self._SLOTS[i % len(self._SLOTS)]
            case_no = i // len(self._SLOTS) + 1
            age = self._CLIENT_AGES[(case_no - 1) % len(self._CLIENT_AGES)]
            text = slot.format(age=age, n=case_no)
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
    # Always the fixed-genre generator: the whole point of weekly-plan is a
    # single, unified account genre, so (unlike `draft`) it does not switch
    # to the generic AnthropicDraftGenerator even when an API key is set.
    return DetectiveDraftGenerator()


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(int(hour), int(minute))


def create_weekly_plan(
    topic: str = "妻の浮気調査(30代男性)",
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
