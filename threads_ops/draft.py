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
from .models import Draft, MarketingPlan, ResearchReport, now_iso


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class DraftGenerator(Protocol):
    name: str

    def generate(
        self,
        report: ResearchReport,
        topic: str,
        count: int,
        marketing_plan: MarketingPlan | None = None,
    ) -> list[str]:
        ...


class TemplateDraftGenerator:
    """Offline, deterministic draft generator based on research keywords.

    When a MarketingPlan is supplied, its tone selects casual vs. polite
    phrasing and its growth_tactics are woven in as calls to action --
    that's the marketing department's plan flowing through to the copy.
    """

    name = "template"

    _OPENERS_CASUAL = [
        "{topic}について話そう。",
        "最近気づいたこと: {topic}",
        "{topic}で伸びる投稿の共通点、知ってますか?",
        "{topic}を始める前に知っておきたいこと。",
    ]

    _CLOSERS_CASUAL = [
        "みなさんはどう思いますか?コメントで教えてください。",
        "続きはリプ欄で。",
        "保存して後で見返してください。",
        "他にも気づいたことがあれば教えてください。",
    ]

    _OPENERS_POLITE = [
        "{topic}について、今日はご紹介します。",
        "最近気づいたことを、{topic}の観点でまとめました。",
        "{topic}で伸びる投稿には、いくつか共通点があります。",
        "{topic}を始める前に知っておきたいポイントをご紹介します。",
    ]

    _CLOSERS_POLITE = [
        "皆様のご意見をコメントでお聞かせください。",
        "詳細はリプライ欄にてご案内します。",
        "ぜひ保存していただき、後ほどご確認ください。",
        "お気づきの点があれば、ぜひ教えてください。",
    ]

    def generate(
        self,
        report: ResearchReport,
        topic: str,
        count: int,
        marketing_plan: MarketingPlan | None = None,
    ) -> list[str]:
        keywords = [kw for kw, _ in report.top_keywords[:5]]
        if marketing_plan and marketing_plan.hashtag_strategy:
            hashtags = marketing_plan.hashtag_strategy[:3]
        else:
            hashtags = [f"#{h}" for h, _ in report.top_hashtags[:3]]

        polite = bool(marketing_plan and marketing_plan.tone == "詳しく丁寧")
        openers = self._OPENERS_POLITE if polite else self._OPENERS_CASUAL
        closers = self._CLOSERS_POLITE if polite else self._CLOSERS_CASUAL
        tactics = marketing_plan.growth_tactics if marketing_plan else []

        drafts = []
        for i in range(count):
            opener = openers[i % len(openers)].format(topic=topic)
            closer = closers[i % len(closers)]
            body_bits = []
            if keywords:
                body_bits.append("注目ワード: " + " / ".join(keywords[:3]))
            if report.best_hours_utc:
                best_hour = report.best_hours_utc[0][0]
                body_bits.append(f"反応が良い時間帯の目安(UTC {best_hour}時)にも投稿してみましょう。")
            if tactics:
                body_bits.append("施策: " + tactics[i % len(tactics)])
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

    def generate(
        self,
        report: ResearchReport,
        topic: str,
        count: int,
        marketing_plan: MarketingPlan | None = None,
    ) -> list[str]:
        import anthropic  # imported lazily so the package is optional

        client = anthropic.Anthropic(api_key=self.api_key)
        keywords = ", ".join(kw for kw, _ in report.top_keywords[:8])
        hashtags = ", ".join(f"#{h}" for h, _ in report.top_hashtags[:5])

        marketing_guidance = ""
        if marketing_plan:
            hashtags = ", ".join(marketing_plan.hashtag_strategy) or hashtags
            tactics = "\n".join(f"- {t}" for t in marketing_plan.growth_tactics)
            marketing_guidance = textwrap.dedent(f"""

                マーケティング方針:
                - トーン: {marketing_plan.tone}
                - 成長施策(いずれかを取り入れる):
                {tactics or "- なし"}
            """)

        prompt = textwrap.dedent(f"""\
            あなたはThreads(Meta)運用担当のマーケターです。
            以下の競合リサーチ結果を踏まえて、トピック「{topic}」についての
            Threads投稿文案を{count}件作成してください。

            リサーチ結果:
            - よく使われるキーワード: {keywords or "なし"}
            - よく使われるハッシュタグ: {hashtags or "なし"}
            - 平均投稿文字数: {report.avg_post_length}
            {marketing_guidance}
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
    marketing_plan: MarketingPlan | None = None,
) -> list[Draft]:
    generator = generator or get_default_generator()
    pending_dir = pending_dir or config.PENDING_DIR

    texts = generator.generate(report, topic, count, marketing_plan=marketing_plan)
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
