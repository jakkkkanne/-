"""Command-line entry point.

    python -m threads_ops research
    python -m threads_ops draft --topic "..." --count 3
    python -m threads_ops review
    python -m threads_ops publish
    python -m threads_ops run-all --topic "..." --count 3

Company departments (built on top of the pipeline above):

    python -m threads_ops marketing
    python -m threads_ops strategy
    python -m threads_ops secretary --topics 3 --count 2
"""

from __future__ import annotations

import argparse
import sys

from . import approval, config, draft, marketing, publish, research, secretary, strategy


def cmd_research(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report, path = research.run_research()
    print(f"競合投稿 {report.post_count} 件を分析しました ({len(report.accounts_analyzed)} アカウント)")
    print(f"レポート保存先: {path}")
    if report.top_keywords:
        print("上位キーワード:", ", ".join(k for k, _ in report.top_keywords[:5]))
    if report.top_hashtags:
        print("上位ハッシュタグ:", ", ".join(f"#{h}" for h, _ in report.top_hashtags[:5]))


def cmd_draft(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report = research.latest_report()
    if report is None:
        print("リサーチレポートがありません。先に `research` を実行してください。", file=sys.stderr)
        raise SystemExit(1)
    drafts = draft.create_drafts(report, topic=args.topic, count=args.count)
    print(f"{len(drafts)} 件の下書きを作成しました (承認待ち):")
    for d in drafts:
        print(f"  - {d.id}")


def cmd_review(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    counts = approval.interactive_review()
    print(f"\n承認: {counts['approved']} / 却下: {counts['rejected']} / 保留: {counts['skipped']}")


def cmd_publish(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    results = publish.publish_approved()
    if not results:
        print("公開待ち(承認済み)の下書きはありません。")
        return
    for r in results:
        status = "成功" if r.success else "失敗"
        print(f"  - {r.draft_id}: {status} ({r.detail})")


def cmd_run_all(args: argparse.Namespace) -> None:
    cmd_research(args)
    cmd_draft(args)
    cmd_review(args)
    cmd_publish(args)


def cmd_marketing(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report = research.latest_report()
    if report is None:
        print("リサーチレポートがありません。先に `research` を実行してください。", file=sys.stderr)
        raise SystemExit(1)
    plan, path = marketing.run_marketing(report)
    print(f"マーケティングプラン保存先: {path}")
    print(f"トーン: {plan.tone} / 投稿頻度: 週{plan.posting_cadence_per_week}件")
    if plan.hashtag_strategy:
        print("推奨ハッシュタグ:", " ".join(plan.hashtag_strategy))
    for tactic in plan.growth_tactics:
        print(f"  - {tactic}")


def cmd_strategy(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report = research.latest_report()
    if report is None:
        print("リサーチレポートがありません。先に `research` を実行してください。", file=sys.stderr)
        raise SystemExit(1)
    plan = marketing.latest_marketing_plan()
    if plan is None:
        print("マーケティングプランがありません。先に `marketing` を実行してください。", file=sys.stderr)
        raise SystemExit(1)
    strategy_plan, path = strategy.run_strategy(report, plan)
    print(f"戦略プラン保存先: {path}")
    print("コンテンツの柱:", ", ".join(strategy_plan.content_pillars))
    print("優先トピック:", ", ".join(strategy_plan.priority_topics))
    print("KPI目標:", strategy_plan.kpi_targets)
    print(strategy_plan.notes)


def cmd_secretary(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report, path = secretary.run_company_cycle(topic_count=args.topics, drafts_per_topic=args.count)
    print(f"会社運用レポート保存先: {path}")
    for dept, summary in report.department_summaries.items():
        print(f"[{dept}] {summary}")
    print("作成した下書きID:", ", ".join(report.draft_ids) if report.draft_ids else "なし")
    print("次のアクション:")
    for action in report.next_actions:
        print(f"  - {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="threads-ops", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("research", help="競合アカウントデータを分析してレポートを作成").set_defaults(func=cmd_research)

    p_draft = sub.add_parser("draft", help="最新レポートから下書きを生成")
    p_draft.add_argument("--topic", required=True, help="投稿のトピック/テーマ")
    p_draft.add_argument("--count", type=int, default=3, help="生成する下書きの数")
    p_draft.set_defaults(func=cmd_draft)

    sub.add_parser("review", help="下書きをCLIで確認し承認/却下").set_defaults(func=cmd_review)
    sub.add_parser("publish", help="承認済みの下書きを投稿(既定はモック)").set_defaults(func=cmd_publish)

    p_all = sub.add_parser("run-all", help="research -> draft -> review -> publish を一括実行")
    p_all.add_argument("--topic", required=True, help="投稿のトピック/テーマ")
    p_all.add_argument("--count", type=int, default=3, help="生成する下書きの数")
    p_all.set_defaults(func=cmd_run_all)

    sub.add_parser("marketing", help="[マーケティング部門] 最新レポートからマーケティングプランを作成").set_defaults(
        func=cmd_marketing
    )
    sub.add_parser("strategy", help="[戦略部門] レポート+マーケティングプランから戦略プランを作成").set_defaults(
        func=cmd_strategy
    )

    p_secretary = sub.add_parser(
        "secretary",
        help="[秘書部門] research -> marketing -> strategy -> draft を統括して一括実行",
    )
    p_secretary.add_argument("--topics", type=int, default=3, help="下書きを作成する優先トピック数")
    p_secretary.add_argument("--count", type=int, default=2, help="トピックごとに生成する下書きの数")
    p_secretary.set_defaults(func=cmd_secretary)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
