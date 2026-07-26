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
