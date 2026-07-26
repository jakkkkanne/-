from threads_ops import approval, storage
from threads_ops.models import Draft


def _make_pending_draft(pending_dir, text="テスト投稿本文", topic="朝活"):
    d = Draft(
        id=storage.new_id("draft"),
        topic=topic,
        text=text,
        created_at="2026-07-26T00:00:00+00:00",
        status="pending",
    )
    storage.write_json(pending_dir / f"{d.id}.json", d.to_dict())
    return d


def test_interactive_review_approve_moves_file(tmp_dirs):
    d = _make_pending_draft(tmp_dirs["pending"])
    inputs = iter(["a"])

    counts = approval.interactive_review(
        pending_dir=tmp_dirs["pending"],
        approved_dir=tmp_dirs["approved"],
        rejected_dir=tmp_dirs["rejected"],
        input_func=lambda _: next(inputs),
        print_func=lambda *_: None,
    )

    assert counts == {"approved": 1, "rejected": 0, "skipped": 0}
    assert not (tmp_dirs["pending"] / f"{d.id}.json").exists()
    approved = storage.read_json(tmp_dirs["approved"] / f"{d.id}.json")
    assert approved["status"] == "approved"


def test_interactive_review_reject_moves_file(tmp_dirs):
    d = _make_pending_draft(tmp_dirs["pending"])
    inputs = iter(["r"])

    counts = approval.interactive_review(
        pending_dir=tmp_dirs["pending"],
        approved_dir=tmp_dirs["approved"],
        rejected_dir=tmp_dirs["rejected"],
        input_func=lambda _: next(inputs),
        print_func=lambda *_: None,
    )

    assert counts == {"approved": 0, "rejected": 1, "skipped": 0}
    rejected = storage.read_json(tmp_dirs["rejected"] / f"{d.id}.json")
    assert rejected["status"] == "rejected"


def test_interactive_review_edit_then_approve(tmp_dirs):
    d = _make_pending_draft(tmp_dirs["pending"], text="元の文章")
    inputs = iter(["e", "編集後の文章", "a"])

    approval.interactive_review(
        pending_dir=tmp_dirs["pending"],
        approved_dir=tmp_dirs["approved"],
        rejected_dir=tmp_dirs["rejected"],
        input_func=lambda _: next(inputs),
        print_func=lambda *_: None,
    )

    approved = storage.read_json(tmp_dirs["approved"] / f"{d.id}.json")
    assert approved["text"] == "編集後の文章"
    assert approved["status"] == "approved"


def test_interactive_review_quit_leaves_remaining_pending(tmp_dirs):
    _make_pending_draft(tmp_dirs["pending"], text="A")
    _make_pending_draft(tmp_dirs["pending"], text="B")
    inputs = iter(["q"])

    counts = approval.interactive_review(
        pending_dir=tmp_dirs["pending"],
        approved_dir=tmp_dirs["approved"],
        rejected_dir=tmp_dirs["rejected"],
        input_func=lambda _: next(inputs),
        print_func=lambda *_: None,
    )

    assert counts == {"approved": 0, "rejected": 0, "skipped": 0}
    assert len(list(tmp_dirs["pending"].glob("*.json"))) == 2
