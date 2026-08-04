from threads_ops import publish, storage
from threads_ops.models import Draft


def _make_approved_draft(approved_dir, text="投稿する本文"):
    d = Draft(
        id=storage.new_id("draft"),
        topic="朝活",
        text=text,
        created_at="2026-07-26T00:00:00+00:00",
        status="approved",
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

    entries = storage.read_jsonl(tmp_dirs["history"])
    assert len(entries) == 1
    assert entries[0]["draft_id"] == d.id
    assert entries[0]["success"] is True


def test_real_publisher_requires_credentials(monkeypatch):
    monkeypatch.setattr("threads_ops.config.THREADS_ACCESS_TOKEN", None)
    monkeypatch.setattr("threads_ops.config.THREADS_USER_ID", None)
    try:
        publish.ThreadsAPIPublisher()
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
