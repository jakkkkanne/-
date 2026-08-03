"""Command-line entry point.

    python -m threads_ops research
    python -m threads_ops draft --topic "..." --count 3
    python -m threads_ops review
    python -m threads_ops publish
    python -m threads_ops run-all --topic "..." --count 3
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import approval, config, draft, publish, research


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


def cmd_weekly_plan(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    drafts = draft.create_weekly_plan(
        topic=args.topic,
        posts_per_day=args.posts_per_day,
        days=args.days,
        start_date=start_date,
    )
    print(f"{len(drafts)} 件の下書きを作成しました ({args.days}日 x 1日{args.posts_per_day}投稿、承認待ち):")
    for d in drafts:
        print(f"  - {d.id}  予定: {d.scheduled_at}")
    print("\n`review` で内容を確認・承認し、`publish` を毎日実行すると予定時刻が来たものだけ投稿されます。")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="threads-ops", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("research", help="競合アカウントデータを分析してレポートを作成").set_defaults(func=cmd_research)

    p_draft = sub.add_parser("draft", help="最新レポートから下書きを生成")
    p_draft.add_argument("--topic", required=True, help="投稿のトピック/テーマ")
    p_draft.add_argument("--count", type=int, default=3, help="生成する下書きの数")
    p_draft.set_defaults(func=cmd_draft)

    p_weekly = sub.add_parser(
        "weekly-plan", help="1日N投稿 x 1週間分の下書きをまとめて生成(既定: 6投稿/日 x 7日、探偵アカウント向け)"
    )
    p_weekly.add_argument(
        "--topic", default="妻の浮気調査(30代男性)", help="下書きに記録するトピック名(既定: 妻の浮気調査(30代男性))"
    )
    p_weekly.add_argument("--posts-per-day", type=int, default=6, help="1日あたりの投稿数(既定: 6)")
    p_weekly.add_argument("--days", type=int, default=7, help="生成する日数(既定: 7)")
    p_weekly.add_argument("--start-date", default=None, help="開始日 YYYY-MM-DD(既定: 今日、JST)")
    p_weekly.set_defaults(func=cmd_weekly_plan)

    sub.add_parser("review", help="下書きをCLIで確認し承認/却下").set_defaults(func=cmd_review)
    sub.add_parser("publish", help="承認済みの下書きを投稿(既定はモック)").set_defaults(func=cmd_publish)

    p_all = sub.add_parser("run-all", help="research -> draft -> review -> publish を一括実行")
    p_all.add_argument("--topic", required=True, help="投稿のトピック/テーマ")
    p_all.add_argument("--count", type=int, default=3, help="生成する下書きの数")
    p_all.set_defaults(func=cmd_run_all)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
