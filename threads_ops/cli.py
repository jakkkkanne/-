"""Command-line entry point.

    python -m threads_ops research
    python -m threads_ops draft --topic "..." --count 3
    python -m threads_ops review
    python -m threads_ops publish
    python -m threads_ops run-all --topic "..." --count 3

Company departments (built on top of the pipeline above):

    python -m threads_ops marketing
    python -m threads_ops strategy
    python -m threads_ops finance
    python -m threads_ops secretary --topics 3 --count 2
    python -m threads_ops secretary --loop --interval-hours 24 --max-iterations 3
"""

from __future__ import annotations

import argparse
import sys

from . import approval, config, draft, finance, marketing, publish, research, secretary, strategy


def cmd_research(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    report, path = research.run_research()
    print(f"[リサーチ部門 - {research.AGENT_NAME}]")
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
    plan = marketing.latest_marketing_plan()
    drafts = draft.create_drafts(report, topic=args.topic, count=args.count, marketing_plan=plan)
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
    print(f"[マーケティング部門 - {marketing.AGENT_NAME}]")
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
    print(f"[戦略部門 - {strategy.AGENT_NAME}]")
    print(f"戦略プラン保存先: {path}")
    print("コンテンツの柱:", ", ".join(strategy_plan.content_pillars))
    print("優先トピック:", ", ".join(strategy_plan.priority_topics))
    print("KPI目標:", strategy_plan.kpi_targets)
    print(strategy_plan.notes)


def cmd_finance(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    strategy_plan = strategy.latest_strategy_plan()
    if strategy_plan is None:
        print("戦略プランがありません。先に `strategy` を実行してください。", file=sys.stderr)
        raise SystemExit(1)
    report, path = finance.run_finance(strategy_plan)
    print(f"[収益管理部門 - {finance.AGENT_NAME}]")
    print(f"収益レポート保存先: {path}")
    print(f"週次目標投稿数: {report.weekly_post_target} / 累計投稿数: {report.posts_published_total}")
    print(f"見込みエンゲージメント収益: {report.estimated_weekly_engagement_value}")
    print(f"見込みフォロワー収益: {report.estimated_weekly_follower_value}")
    print(f"見込み楽天アフィリエイト収益: {report.estimated_weekly_affiliate_revenue}")
    print(f"見込み生成コスト: {report.estimated_weekly_generation_cost}")
    print(f"見込み週次利益: {report.estimated_weekly_profit}")
    print(report.notes)


def _print_company_report(report) -> None:
    for dept, summary in report.department_summaries.items():
        print(f"[{dept}] {summary}")
    print("作成した下書きID:", ", ".join(report.draft_ids) if report.draft_ids else "なし")
    print("次のアクション:")
    for action in report.next_actions:
        print(f"  - {action}")


def cmd_secretary(args: argparse.Namespace) -> None:
    config.ensure_dirs()

    if not args.loop:
        report, path = secretary.run_company_cycle(topic_count=args.topics, drafts_per_topic=args.count)
        print(f"[秘書部門 - {secretary.AGENT_NAME}]")
        print(f"会社運用レポート保存先: {path}")
        _print_company_report(report)
        return

    def on_cycle(report) -> None:
        print(f"\n=== サイクル完了: {report.id} ({report.generated_at}) ===")
        _print_company_report(report)

    interval_seconds = args.interval_hours * 3600
    print(f"[秘書部門 - {secretary.AGENT_NAME}]")
    print(
        f"秘書部門ループを開始します(間隔: {args.interval_hours}時間、"
        f"{'無期限' if args.max_iterations is None else f'{args.max_iterations}回'})。Ctrl+Cで停止できます。"
    )
    secretary.run_company_loop(
        interval_seconds=interval_seconds,
        topic_count=args.topics,
        drafts_per_topic=args.count,
        max_iterations=args.max_iterations,
        on_cycle=on_cycle,
    )


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
    sub.add_parser("finance", help="[収益管理部門] 戦略プランと投稿履歴から週次の見込み利益を試算").set_defaults(
        func=cmd_finance
    )

    p_secretary = sub.add_parser(
        "secretary",
        help="[秘書部門] research -> marketing -> strategy -> finance -> draft を統括して一括実行",
    )
    p_secretary.add_argument("--topics", type=int, default=3, help="下書きを作成する優先トピック数")
    p_secretary.add_argument("--count", type=int, default=2, help="トピックごとに生成する下書きの数")
    p_secretary.add_argument("--loop", action="store_true", help="一定間隔で繰り返し実行する(定期自動運用)")
    p_secretary.add_argument("--interval-hours", type=float, default=24.0, help="--loop 時の実行間隔(時間)")
    p_secretary.add_argument(
        "--max-iterations", type=int, default=None, help="--loop 時の最大実行回数(省略時は無期限)"
    )
    p_secretary.set_defaults(func=cmd_secretary)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
