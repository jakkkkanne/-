"""End-to-end test of the whole company: every department runs, a human
approves the resulting drafts (simulated via approval.interactive_review's
input_func), and only then are they published. Verifies the full chain
research -> marketing -> strategy -> finance -> secretary -> draft ->
review -> publish works together, and that nothing gets published without
going through approval first.
"""

from threads_ops import approval, publish, secretary, storage
from threads_ops.models import CompetitorPost


def _write_competitor_data(tmp_dirs):
    posts = [
        CompetitorPost(
            account="acct_a",
            text="朝活を続けるコツを話します",
            posted_at="2026-07-20T09:00:00+00:00",
            likes=300,
            replies=40,
            reposts=15,
            hashtags=["朝活", "習慣化"],
        ),
        CompetitorPost(
            account="acct_b",
            text="マーケティングの基本を解説します",
            posted_at="2026-07-21T11:00:00+00:00",
            likes=200,
            replies=25,
            reposts=10,
            hashtags=["マーケティング"],
        ),
    ]
    storage.write_json(
        tmp_dirs["competitors"] / "acct.json",
        {"posts": [p.to_dict() for p in posts]},
    )


def test_full_company_cycle_to_publish(tmp_dirs):
    _write_competitor_data(tmp_dirs)

    company_report, _ = secretary.run_company_cycle(topic_count=2, drafts_per_topic=1)
    assert len(company_report.draft_ids) == 2

    pending = approval.list_drafts(tmp_dirs["pending"])
    assert {d.id for d in pending} == set(company_report.draft_ids)

    # Nothing is published before a human approves.
    pre_publish_results = publish.publish_approved(
        publisher=publish.MockPublisher(),
        approved_dir=tmp_dirs["approved"],
        posted_dir=tmp_dirs["posted"],
        history_file=tmp_dirs["history"],
    )
    assert pre_publish_results == []

    # Simulate a human approving every pending draft via the CLI review flow.
    answers = iter(["a"] * len(pending))
    counts = approval.interactive_review(
        pending_dir=tmp_dirs["pending"],
        approved_dir=tmp_dirs["approved"],
        rejected_dir=tmp_dirs["rejected"],
        input_func=lambda _prompt: next(answers),
        print_func=lambda *_a, **_k: None,
    )
    assert counts["approved"] == len(pending)
    assert not list(tmp_dirs["pending"].glob("*.json"))

    results = publish.publish_approved(
        publisher=publish.MockPublisher(),
        approved_dir=tmp_dirs["approved"],
        posted_dir=tmp_dirs["posted"],
        history_file=tmp_dirs["history"],
    )
    assert len(results) == len(pending)
    assert all(r.success for r in results)
    assert not list(tmp_dirs["approved"].glob("*.json"))
    assert len(list(tmp_dirs["posted"].glob("*.json"))) == len(pending)

    history_entries = storage.read_jsonl(tmp_dirs["history"])
    assert len(history_entries) == len(pending)
    assert all(e["success"] for e in history_entries)
