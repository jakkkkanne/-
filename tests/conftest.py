import pytest

from threads_ops import config


@pytest.fixture
def tmp_dirs(tmp_path, monkeypatch):
    """Redirect all data directories to a temp path for isolation."""
    competitors = tmp_path / "competitors"
    reports = tmp_path / "reports"
    pending = tmp_path / "drafts" / "pending"
    approved = tmp_path / "drafts" / "approved"
    rejected = tmp_path / "drafts" / "rejected"
    posted = tmp_path / "drafts" / "posted"
    history = tmp_path / "drafts" / "history.jsonl"
    persona_file = tmp_path / "persona" / "persona.md"

    monkeypatch.setattr(config, "COMPETITORS_DIR", competitors)
    monkeypatch.setattr(config, "REPORTS_DIR", reports)
    monkeypatch.setattr(config, "PENDING_DIR", pending)
    monkeypatch.setattr(config, "APPROVED_DIR", approved)
    monkeypatch.setattr(config, "REJECTED_DIR", rejected)
    monkeypatch.setattr(config, "POSTED_DIR", posted)
    monkeypatch.setattr(config, "HISTORY_FILE", history)
    monkeypatch.setattr(config, "PERSONA_DIR", persona_file.parent)
    monkeypatch.setattr(config, "PERSONA_FILE", persona_file)
    config.ensure_dirs()

    return {
        "competitors": competitors,
        "reports": reports,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "posted": posted,
        "history": history,
        "persona_file": persona_file,
    }
