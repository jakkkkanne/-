"""Human-in-the-loop CLI approval stage.

Nothing is ever posted to Threads without a human explicitly approving
the draft text first. Drafts move between data/drafts/{pending,approved,
rejected}/ as JSON files, so the current state is always visible on disk.
"""

from __future__ import annotations

from collections.abc import Callable

from . import config, storage
from .models import Draft


def list_drafts(directory) -> list[Draft]:
    return [Draft.from_dict(storage.read_json(p)) for p in storage.list_json_files(directory)]


def _move(draft: Draft, from_dir, to_dir, new_status: str) -> None:
    old_path = from_dir / f"{draft.id}.json"
    draft.status = new_status
    storage.write_json(to_dir / f"{draft.id}.json", draft.to_dict())
    if old_path.exists():
        old_path.unlink()


def approve(draft: Draft, pending_dir=None, approved_dir=None) -> None:
    _move(draft, pending_dir or config.PENDING_DIR, approved_dir or config.APPROVED_DIR, "approved")


def reject(draft: Draft, pending_dir=None, rejected_dir=None, note: str | None = None) -> None:
    if note:
        draft.note = note
    _move(draft, pending_dir or config.PENDING_DIR, rejected_dir or config.REJECTED_DIR, "rejected")


def edit_text(draft: Draft, new_text: str, pending_dir=None) -> None:
    pending_dir = pending_dir or config.PENDING_DIR
    draft.text = new_text
    storage.write_json(pending_dir / f"{draft.id}.json", draft.to_dict())


_PROMPT = "[a]pprove / [r]eject / [e]dit / [s]kip / [q]uit > "


def interactive_review(
    pending_dir=None,
    approved_dir=None,
    rejected_dir=None,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> dict[str, int]:
    """Walk pending drafts one by one, prompting for a decision on each."""
    pending_dir = pending_dir or config.PENDING_DIR
    approved_dir = approved_dir or config.APPROVED_DIR
    rejected_dir = rejected_dir or config.REJECTED_DIR

    counts = {"approved": 0, "rejected": 0, "skipped": 0}
    drafts = list_drafts(pending_dir)

    if not drafts:
        print_func("承認待ちの下書きはありません。")
        return counts

    for idx, draft in enumerate(drafts, start=1):
        print_func(f"\n--- 下書き {idx}/{len(drafts)} (topic: {draft.topic}, generator: {draft.generator}) ---")
        print_func(draft.text)
        print_func(f"({len(draft.text)} 文字)")

        while True:
            choice = input_func(_PROMPT).strip().lower()
            if choice in ("a", "approve"):
                approve(draft, pending_dir, approved_dir)
                counts["approved"] += 1
                break
            if choice in ("r", "reject"):
                reject(draft, pending_dir, rejected_dir)
                counts["rejected"] += 1
                break
            if choice in ("e", "edit"):
                new_text = input_func("新しい本文を入力してください:\n")
                edit_text(draft, new_text, pending_dir)
                print_func("更新しました。再度確認してください。")
                print_func(draft.text)
                continue
            if choice in ("s", "skip"):
                counts["skipped"] += 1
                break
            if choice in ("q", "quit"):
                return counts
            print_func("入力が不正です。a/r/e/s/q のいずれかを入力してください。")

    return counts
