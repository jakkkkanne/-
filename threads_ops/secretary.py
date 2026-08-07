"""Secretary department.

Oversees the other departments -- research, marketing, strategy, finance --
and runs them in sequence, then hands the strategy department's priority
topics to the draft stage. Drafts still land in data/drafts/pending/ and
require a human's approval via `review`; the secretary never approves or
publishes anything itself.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from . import config, draft, finance, marketing, research, storage, strategy
from .models import CompanyReport, now_iso

AGENT_NAME = "ミナ"  # 秘書部門担当(各部門を統括)

_POLITE_MARKERS = ("です。", "ます。", "でした。", "ください。")


def qa_check_thread(segments: list[str]) -> list[str]:
    """ミナ's pre-delivery checklist for one thread: typos, tone, readability.

    Returns human-readable issues found (empty list = passed). This is a
    mechanical safety net -- doubled punctuation, unbalanced [brackets],
    stray whitespace, a polite segment breaking an otherwise casual
    thread, a wall of text with no line breaks -- not a substitute for
    actually reading the copy, which ミナ (and the operator) still does
    before delivery.
    """
    issues: list[str] = []
    if not segments:
        return ["セグメントが空です。"]

    casual_count = sum(1 for s in segments if not any(m in s for m in _POLITE_MARKERS))
    if 0 < casual_count < len(segments):
        issues.append("敬体(です/ます)とカジュアルな口調が混在しています。トーンを統一してください。")

    for i, segment in enumerate(segments, start=1):
        if segment != segment.strip():
            issues.append(f"セグメント{i}: 前後に余分な空白/改行があります。")
        if "  " in segment:
            issues.append(f"セグメント{i}: 連続した空白があります。")
        if "。。" in segment or "、、" in segment:
            issues.append(f"セグメント{i}: 句読点が連続しています。")
        if segment.count("[") != segment.count("]"):
            issues.append(f"セグメント{i}: []の対応が取れていません。")
        if draft.visible_length(segment) > config.THREADS_MAX_CHARS:
            issues.append(f"セグメント{i}: 文字数が上限を超えています({draft.visible_length(segment)}文字)。")
        if len(segment) > 80 and "\n" not in segment:
            issues.append(f"セグメント{i}: 改行がなく読みにくい可能性があります。")

    return issues


def qa_check_threads(threads: list[dict]) -> dict[str, list[str]]:
    """Batch qa_check_thread over カイ's product threads, keyed by product_name.

    Only entries with at least one issue are included.
    """
    flagged = {}
    for thread in threads:
        issues = qa_check_thread(thread["segments"])
        if issues:
            flagged[thread["product_name"]] = issues
    return flagged


def run_company_cycle(topic_count: int = 3, drafts_per_topic: int = 2) -> tuple[CompanyReport, str]:
    config.ensure_dirs()

    report, _ = research.run_research()
    marketing_plan, _ = marketing.run_marketing(report)
    strategy_plan, _ = strategy.run_strategy(report, marketing_plan)
    revenue_report, _ = finance.run_finance(strategy_plan)

    topics = strategy_plan.priority_topics[:topic_count]
    draft_ids: list[str] = []
    for topic in topics:
        drafts = draft.create_drafts(
            report, topic=topic, count=drafts_per_topic, marketing_plan=marketing_plan
        )
        draft_ids.extend(d.id for d in drafts)

    if report.day_hour_performance:
        w, h, score, _cnt = report.day_hour_performance[0]
        best_slot_note = f"最強スロット: {w}曜{h}時(平均エンゲージメント{score})"
    else:
        best_slot_note = "曜日x時間帯の実績データ不足"

    summaries = {
        "research": (
            f"[{research.AGENT_NAME}] {report.post_count}件の投稿を{len(report.accounts_analyzed)}アカウント分析"
            f"(文章のみ{report.text_only_post_count}件)。{best_slot_note}"
        ),
        "marketing": (
            f"[{marketing.AGENT_NAME}] 投稿トーン: {marketing_plan.tone} / 週{marketing_plan.posting_cadence_per_week}件目安"
            f" / 伸びる型予測: {marketing_plan.predicted_trending_type or '不明'}"
            f" / ターゲット共鳴型: {marketing_plan.target_resonant_type or '不明'}"
        ),
        "strategy": (
            f"[{strategy.AGENT_NAME}] 優先トピック: {', '.join(strategy_plan.priority_topics)}"
            f" / 曜日x時間帯カレンダー{len(strategy_plan.weekly_calendar)}枠を作成"
        ),
        "finance": f"[{finance.AGENT_NAME}] 週次見込み利益: {revenue_report.estimated_weekly_profit}(投稿累計{revenue_report.posts_published_total}件)",
        "secretary": f"[{AGENT_NAME}] {len(topics)}トピックに対し計{len(draft_ids)}件の下書きを作成",
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
        finance_report_id=revenue_report.id,
        department_summaries=summaries,
        draft_ids=draft_ids,
        next_actions=next_actions,
    )
    path = save_company_report(company_report)
    return company_report, path


def run_company_loop(
    interval_seconds: float,
    topic_count: int = 3,
    drafts_per_topic: int = 2,
    max_iterations: int | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
    on_cycle: Callable[[CompanyReport], None] | None = None,
) -> list[CompanyReport]:
    """Run run_company_cycle repeatedly, sleeping interval_seconds in between.

    Only the research -> marketing -> strategy -> finance -> draft stages
    run unattended; review/publish are never called here, so a human is
    still required before anything is posted. max_iterations=None loops
    forever (interrupt with Ctrl+C); pass a number to bound it (used by
    tests and for a "run N cycles" invocation).
    """
    reports: list[CompanyReport] = []
    i = 0
    while max_iterations is None or i < max_iterations:
        report, _ = run_company_cycle(topic_count=topic_count, drafts_per_topic=drafts_per_topic)
        reports.append(report)
        if on_cycle:
            on_cycle(report)
        i += 1
        if max_iterations is None or i < max_iterations:
            sleep_func(interval_seconds)
    return reports


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
