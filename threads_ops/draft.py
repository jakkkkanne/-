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
from typing import Protocol

from . import config, storage
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
