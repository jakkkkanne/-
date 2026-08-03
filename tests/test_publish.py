from datetime import datetime, timezone

from threads_ops import publish, storage
from threads_ops.models import Draft


def _make_approved_draft(approved_dir, text="投稿する本文", scheduled_at=None):
    d = Draft(
        id=storage.new_id("draft"),
        topic="朝活",
        text=text,
        created_at="2026-07-26T00:00:00+00:00",
        status="approved",
        scheduled_at=scheduled_at,
    )
    storage.write_json(approved_dir / f"{d.id}.json", d.to_dict())
    return d


def test_mock_publisher_never_calls_network_and_reports_success():
    d = Draft(
        id="draft_x",
        topic="t",
        text="hello",
        created_at="2026-07-26T00:00:00+00:00",
        status="approved",
    )
    result = publish.MockPublisher().publish(d)
    assert result.success is True
    assert result.post_id == "mock_draft_x"


def test_publish_approved_moves_to_posted_and_records_history(tmp_dirs):
    d = _make_approved_draft(tmp_dirs["approved"])

    results = publish.publish_approved(
        publisher=publish.MockPublisher(),
        approved_dir=tmp_dirs["approved"],
        posted_dir=tmp_dirs["posted"],
        history_file=tmp_dirs["history"],
    )

    assert len(results) == 1
    assert results[0].success is True
    assert not (tmp_dirs["approved"] / f"{d.id}.json").exists()
    posted = storage.read_json(tmp_dirs["posted"] / f"{d.id}.json")
    assert posted["status"] == "posted"
    assert tmp_dirs["history"].exists()
    history_lines = tmp_dirs["history"].read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 1


def test_publish_approved_holds_drafts_scheduled_in_the_future(tmp_dirs):
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    due = _make_approved_draft(tmp_dirs["approved"], text="due", scheduled_at="2026-08-03T09:00:00+00:00")
    future = _make_approved_draft(tmp_dirs["approved"], text="future", scheduled_at="2026-08-04T09:00:00+00:00")

    results = publish.publish_approved(
        publisher=publish.MockPublisher(),
        approved_dir=tmp_dirs["approved"],
        posted_dir=tmp_dirs["posted"],
        history_file=tmp_dirs["history"],
        now=now,
    )

    assert [r.draft_id for r in results] == [due.id]
    assert not (tmp_dirs["approved"] / f"{due.id}.json").exists()
    assert (tmp_dirs["approved"] / f"{future.id}.json").exists()


def test_real_publisher_requires_credentials(monkeypatch):
    monkeypatch.setattr("threads_ops.config.THREADS_ACCESS_TOKEN", None)
    monkeypatch.setattr("threads_ops.config.THREADS_USER_ID", None)
    try:
        publish.ThreadsAPIPublisher()
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
