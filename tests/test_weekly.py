import json
from datetime import date

import pytest

from threads_ops import weekly


def _fake_items():
    return [
        {"day": i + 1, "type": t, "text": f"本文{i + 1}", "aim": f"狙い{i + 1}"}
        for i, (t, _hint) in enumerate(weekly.POST_TYPES)
    ]


def test_create_weekly_posts_requires_a_persona(tmp_dirs):
    with pytest.raises(RuntimeError):
        weekly.create_weekly_posts(persona_text=None, pending_dir=tmp_dirs["pending"])


def test_create_weekly_posts_saves_seven_scheduled_drafts(tmp_dirs, monkeypatch):
    monkeypatch.setattr(weekly, "_call_claude", lambda prompt, api_key=None, model=None: json.dumps(_fake_items()))

    drafts = weekly.create_weekly_posts(
        persona_text="ダミーペルソナ",
        start_date=date(2026, 8, 3),
        post_time="08:00",
        pending_dir=tmp_dirs["pending"],
    )

    assert len(drafts) == 7
    saved = list(tmp_dirs["pending"].glob("*.json"))
    assert len(saved) == 7

    for i, d in enumerate(drafts):
        assert d.status == "pending"
        assert d.generator == "weekly_persona"
        assert d.post_type == weekly.POST_TYPES[i][0]
        assert d.aim == f"狙い{i + 1}"
        assert d.scheduled_at == f"2026-08-{3 + i:02d}T08:00:00+09:00"


def test_create_weekly_posts_rejects_wrong_item_count(tmp_dirs, monkeypatch):
    monkeypatch.setattr(
        weekly, "_call_claude", lambda prompt, api_key=None, model=None: json.dumps(_fake_items()[:5])
    )

    with pytest.raises(ValueError):
        weekly.create_weekly_posts(persona_text="ダミーペルソナ", pending_dir=tmp_dirs["pending"])


def test_parse_weekly_response_strips_code_fence():
    wrapped = "```json\n" + json.dumps(_fake_items()) + "\n```"
    items = weekly._parse_weekly_response(wrapped)

    assert len(items) == 7
    assert items[0]["type"] == "悩み共感型"
