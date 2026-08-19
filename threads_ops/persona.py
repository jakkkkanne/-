"""Persona generation stage (prompt ①).

Turns a single fixed personal experience into a reusable storytelling
persona -- a handful of sample story patterns, each tagged with which
reader it lands with. This is generated once via
`python -m threads_ops persona` and saved to disk; every later run of
`weekly.create_weekly_posts` (prompt ②) loads the saved file and uses it
as a style/voice reference instead of regenerating it from scratch.
"""

from __future__ import annotations

import textwrap

from . import config

DEFAULT_EXPERIENCE = "妻に不倫をされ探偵を雇い証拠を確保し慰謝料請求"
DEFAULT_SUPPLEMENT = ""

PERSONA_PROMPT_TEMPLATE = textwrap.dedent("""\
    # 役割
    あなたはストーリーテリングの専門家です。
    平凡な出来事を、人の心を動かすエピソードに再構成するのが得意です。

    # 私の体験
    【{experience}】
    ※補足:{supplement}

    # 指示
    この体験を、Threadsで反応が取れるストーリー投稿に仕立ててください。
    以下の「感情の流れ」を必ず作ること。

    ① 共感のフック(読者が「自分のことだ」と思う1行から始める)
    ② どん底(うまくいかなかった時期の描写。具体的に)
    ③ 転機(何に気づいたか/何を変えたか)
    ④ 変化(その結果どうなったか。盛らず、等身大で)
    ⑤ メッセージ(読者の背中をそっと押す一言で締める)

    # 条件
    ・自慢・マウントに見せない(あくまで等身大)
    ・数字を1つは入れて具体性を出す
    ・120文字以内、改行多め、テンポよく
    ・「すごいでしょ」ではなく「あなたもできる」と思わせる
    ・日本語のみ

    # 出力
    上記の流れで投稿を3パターン作り、
    それぞれ「どの読者に一番刺さるか」を添えてください。
""")


def build_persona_prompt(experience: str = DEFAULT_EXPERIENCE, supplement: str = DEFAULT_SUPPLEMENT) -> str:
    return PERSONA_PROMPT_TEMPLATE.format(experience=experience, supplement=supplement)


def generate_persona(
    experience: str = DEFAULT_EXPERIENCE,
    supplement: str = DEFAULT_SUPPLEMENT,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    import anthropic  # imported lazily so the package is optional

    client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
    prompt = build_persona_prompt(experience, supplement)
    response = client.messages.create(
        model=model or config.ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def save_persona(text: str, path=None) -> str:
    path = path or config.PERSONA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def load_persona(path=None) -> str | None:
    path = path or config.PERSONA_FILE
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def build_and_save_persona(
    experience: str = DEFAULT_EXPERIENCE,
    supplement: str = DEFAULT_SUPPLEMENT,
    path=None,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str, str]:
    text = generate_persona(experience, supplement, api_key=api_key, model=model)
    saved_path = save_persona(text, path=path)
    return text, saved_path
