"""Command-line entry point.

    python -m threads_ops research
    python -m threads_ops draft --topic "..." --count 3
    python -m threads_ops persona
    python -m threads_ops weekly-plan
    python -m threads_ops review
    python -m threads_ops publish
    python -m threads_ops run-all --topic "..." --count 3
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import approval, config, draft, persona, publish, research, weekly


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


def cmd_persona(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    if not config.ANTHROPIC_API_KEY:
        print("エラー: ペルソナ生成には ANTHROPIC_API_KEY が必要です。.env に設定してください。", file=sys.stderr)
        raise SystemExit(1)
    text, path = persona.build_and_save_persona(experience=args.experience, supplement=args.supplement or "")
    print(f"ペルソナを生成し保存しました: {path}\n")
    print(text)
    print("\n以降 `weekly-plan` はこのファイルを毎回参照します。作り直す場合はこのコマンドを再実行してください。")


def cmd_weekly_plan(args: argparse.Namespace) -> None:
    config.ensure_dirs()
    if not config.ANTHROPIC_API_KEY:
        print("エラー: weekly-plan には ANTHROPIC_API_KEY が必要です。.env に設定してください。", file=sys.stderr)
        raise SystemExit(1)
    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    try:
        drafts = weekly.create_weekly_posts(
            theme=args.theme,
            genre=args.genre,
            tone=args.tone,
            start_date=start_date,
            post_time=args.post_time,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

    print(f"{len(drafts)} 件の下書きを作成しました (1日1投稿 x 1週間、承認待ち):")
    for d in drafts:
        print(f"  - {d.id}  {d.scheduled_at}  [{d.post_type}]")
        print(f"    {d.text}")
        if d.aim:
            print(f"    (狙い: {d.aim})")
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

    p_persona = sub.add_parser(
        "persona", help="固定の体験談からアカウントのペルソナ(語り口のサンプル)を生成して保存"
    )
    p_persona.add_argument(
        "--experience", default=persona.DEFAULT_EXPERIENCE, help="ペルソナの元になる体験(既定: 妻に不倫をされ探偵を雇い証拠を確保し慰謝料請求)"
    )
    p_persona.add_argument("--supplement", default=None, help="体験の補足情報(任意)")
    p_persona.set_defaults(func=cmd_persona)

    p_weekly = sub.add_parser(
        "weekly-plan", help="ペルソナを参考に1日1投稿 x 1週間分(7本)の下書きを生成(要: persona を先に実行)"
    )
    p_weekly.add_argument("--theme", default=weekly.DEFAULT_THEME, help=f"投稿テーマ(既定: {weekly.DEFAULT_THEME})")
    p_weekly.add_argument("--genre", default=weekly.DEFAULT_GENRE, help=f"アカウントのジャンル(既定: {weekly.DEFAULT_GENRE})")
    p_weekly.add_argument("--tone", default=weekly.DEFAULT_TONE, help=f"アカウントの口調(既定: {weekly.DEFAULT_TONE})")
    p_weekly.add_argument("--post-time", default=weekly.DEFAULT_POST_TIME, help="毎日の投稿予定時刻 HH:MM、JST(既定: 08:00)")
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
