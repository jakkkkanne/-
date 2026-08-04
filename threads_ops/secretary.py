"""Secretary department.

Oversees the other departments -- research, marketing, strategy -- and runs
them in sequence, then hands the strategy department's priority topics to
the draft stage. Drafts still land in data/drafts/pending/ and require a
human's approval via `review`; the secretary never approves or publishes
anything itself.
"""

from __future__ import annotations

from . import config, draft, marketing, research, storage, strategy
from .models import CompanyReport, now_iso


def run_company_cycle(topic_count: int = 3, drafts_per_topic: int = 2) -> tuple[CompanyReport, str]:
    config.ensure_dirs()

    report, _ = research.run_research()
    marketing_plan, _ = marketing.run_marketing(report)
    strategy_plan, _ = strategy.run_strategy(report, marketing_plan)

    topics = strategy_plan.priority_topics[:topic_count]
    draft_ids: list[str] = []
    for topic in topics:
        drafts = draft.create_drafts(report, topic=topic, count=drafts_per_topic)
        draft_ids.extend(d.id for d in drafts)

    summaries = {
        "research": f"{report.post_count}件の投稿を{len(report.accounts_analyzed)}アカウント分析",
        "marketing": f"投稿トーン: {marketing_plan.tone} / 週{marketing_plan.posting_cadence_per_week}件目安",
        "strategy": f"優先トピック: {', '.join(strategy_plan.priority_topics)}",
        "secretary": f"{len(topics)}トピックに対し計{len(draft_ids)}件の下書きを作成",
    }

    next_actions = [
        "`python -m threads_ops review` で下書きを確認・承認する",
        "承認後 `python -m threads_ops publish` で投稿する",
    ]

    company_report = CompanyReport(
        id=storage.new_id("company"),
        generated_at=now_iso(),
        research_report_id=report.id,
        marketing_plan_id=marketing_plan.id,
        strategy_plan_id=strategy_plan.id,
        department_summaries=summaries,
        draft_ids=draft_ids,
        next_actions=next_actions,
    )
    path = save_company_report(company_report)
    return company_report, path


def save_company_report(report: CompanyReport, secretary_dir=None) -> str:
    secretary_dir = secretary_dir or config.SECRETARY_DIR
    path = secretary_dir / f"{report.id}.json"
    storage.write_json(path, report.to_dict())
    return str(path)


def latest_company_report(secretary_dir=None) -> CompanyReport | None:
    secretary_dir = secretary_dir or config.SECRETARY_DIR
    files = storage.list_json_files(secretary_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return CompanyReport.from_dict(storage.read_json(latest))
