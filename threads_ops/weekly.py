"""Weekly post generation stage (prompt ②).

Produces one post per day for a week -- 7 posts total, one from each of 7
fixed post "types" -- using the persona saved by persona.py (prompt ①) as
a style/voice reference. Unlike draft.py's generators this needs richer
per-post metadata (type, aim) than the plain DraftGenerator Protocol
returns, so it builds Drafts directly instead of returning bare text.
"""

from __future__ import annotations

import json
import textwrap
from datetime import date, datetime, time as dt_time, timedelta, timezone

from . import config, persona, storage
from .models import Draft, now_iso

JST = timezone(timedelta(hours=9))

DEFAULT_THEME = "不倫する人の共通行動"
DEFAULT_GENRE = "不倫された・浮気された"
DEFAULT_TONE = "やさしく、等身大で偉そうにせず、友達に語りかける様に"
DEFAULT_POST_TIME = "08:00"

# 曜日ごとに必ず1つずつ使う型(プロンプト②の指定順)。
POST_TYPES = [
    ("悩み共感型", "読者の悩みを代弁して刺す"),
    ("実体験型", "自分の失敗や変化を語る"),
    ("ノウハウ型", "具体的な手順・方法を渡す"),
    ("逆張り型", "よくある常識を否定する"),
    ("数字提示型", "具体的な数字で信頼させる"),
    ("質問型", "読者に問いかけてコメントを誘う"),
    ("まとめ型", "保存したくなる総まとめ"),
]

WEEKLY_PROMPT_TEMPLATE = textwrap.dedent("""\
    # 役割
    あなたはThreads運用のプロです。読者の感情を動かす投稿設計が得意です。

    # 前提
    テーマ:【{theme}】
    私のジャンル:【{genre}】
    アカウントの口調:【{tone}】

    # ペルソナ参考(このアカウントのストーリー投稿サンプルと、刺さる読者層)
    {persona_text}

    # 指示
    このテーマで、切り口を変えた投稿を7本(1週間分)作ってください。
    7本は必ず以下の型を1つずつ使うこと。

    1日目:悩み共感型(読者の悩みを代弁して刺す)
    2日目:実体験型(自分の失敗や変化を語る)
    3日目:ノウハウ型(具体的な手順・方法を渡す)
    4日目:逆張り型(よくある常識を否定する)
    5日目:数字提示型(具体的な数字で信頼させる)
    6日目:質問型(読者に問いかけてコメントを誘う)
    7日目:まとめ型(保存したくなる総まとめ)

    # 条件
    ・1本120文字以内、改行を多めに使う
    ・冒頭1行で必ず引きを作る
    ・ハッシュタグ・絵文字の多用はしない
    ・最後は共感か問いかけで締める
    ・AIっぽい硬い言い回しを避け、口語で書く
    ・日本語のみ
    ・絵文字を4〜5個使う
    ・上のペルソナ参考と同じ声・トーンで書くこと

    # 出力形式
    次のJSON配列だけを出力してください。前置き・説明・コードブロック記法(```)は一切不要です。
    [
      {{"day": 1, "type": "悩み共感型", "text": "投稿本文", "aim": "この投稿の狙いを1行で"}},
      ...
      {{"day": 7, "type": "まとめ型", "text": "投稿本文", "aim": "この投稿の狙いを1行で"}}
    ]
""")


def build_weekly_prompt(theme: str, genre: str, tone: str, persona_text: str) -> str:
    return WEEKLY_PROMPT_TEMPLATE.format(theme=theme, genre=genre, tone=tone, persona_text=persona_text)


def _call_claude(prompt: str, api_key: str | None = None, model: str | None = None) -> str:
    import anthropic  # imported lazily so the package is optional

    client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model or config.ANTHROPIC_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def _parse_weekly_response(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json"):]
    items = json.loads(cleaned.strip())
    if not isinstance(items, list):
        raise ValueError("Claude の応答がJSON配列ではありません")
    return items


def create_weekly_posts(
    theme: str = DEFAULT_THEME,
    genre: str = DEFAULT_GENRE,
    tone: str = DEFAULT_TONE,
    start_date: date | None = None,
    post_time: str = DEFAULT_POST_TIME,
    tz: timezone = JST,
    persona_text: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    pending_dir=None,
) -> list[Draft]:
    """Generate the week's 7 posts (1/day) and save them as pending drafts.

    Requires a persona to already exist (see persona.build_and_save_persona)
    -- pass `persona_text` explicitly to bypass the saved file (mainly for
    tests).
    """
    persona_text = persona_text if persona_text is not None else persona.load_persona()
    if not persona_text:
        raise RuntimeError(
            "ペルソナが未生成です。先に `python -m threads_ops persona` を実行してください。"
        )

    pending_dir = pending_dir or config.PENDING_DIR
    start_date = start_date or datetime.now(tz).date()
    hour, minute = (int(p) for p in post_time.split(":"))

    prompt = build_weekly_prompt(theme, genre, tone, persona_text)
    raw = _call_claude(prompt, api_key=api_key, model=model)
    items = _parse_weekly_response(raw)

    if len(items) != len(POST_TYPES):
        raise ValueError(f"Claude から{len(POST_TYPES)}件ではなく{len(items)}件の投稿が返されました")

    drafts = []
    for i, item in enumerate(items):
        current_date = start_date + timedelta(days=i)
        scheduled_at = datetime.combine(current_date, dt_time(hour, minute), tzinfo=tz).isoformat()
        draft = Draft(
            id=storage.new_id("draft"),
            topic=theme,
            text=str(item["text"]).strip(),
            created_at=now_iso(),
            status="pending",
            generator="weekly_persona",
            scheduled_at=scheduled_at,
            post_type=item.get("type"),
            aim=item.get("aim"),
        )
        storage.write_json(pending_dir / f"{draft.id}.json", draft.to_dict())
        drafts.append(draft)

    return drafts
