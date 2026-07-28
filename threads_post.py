#!/usr/bin/env python3
"""Post a single text-only thread via Meta's Threads Graph API.

Credentials are read from environment variables only -- never hardcode a
token into this file or pass it as a plain CLI flag that could end up in
shell history.

Required environment variables:
  THREADS_ACCESS_TOKEN   Long-lived user access token with threads_content_publish
  THREADS_USER_ID        Numeric Threads user id (not the @username)

Optional:
  THREADS_API_BASE       Defaults to https://graph.threads.net/v1.0

Usage:
  export THREADS_ACCESS_TOKEN=...
  export THREADS_USER_ID=...
  python threads_post.py "投稿したいテキスト"
  echo "投稿したいテキスト" | python threads_post.py
"""

from __future__ import annotations

import os
import sys

import requests

API_BASE = os.environ.get("THREADS_API_BASE", "https://graph.threads.net/v1.0")


def post_thread(text: str, access_token: str, user_id: str) -> str:
    """Create + publish a text thread using the official two-step flow."""
    create_resp = requests.post(
        f"{API_BASE}/{user_id}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": access_token},
        timeout=30,
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    publish_resp = requests.post(
        f"{API_BASE}/{user_id}/threads_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()["id"]


def main() -> None:
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    if not access_token or not user_id:
        print(
            "エラー: 環境変数 THREADS_ACCESS_TOKEN と THREADS_USER_ID を設定してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    text = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not text:
        print("エラー: 投稿するテキストを引数か標準入力で渡してください。", file=sys.stderr)
        sys.exit(1)

    try:
        post_id = post_thread(text, access_token, user_id)
    except Exception as exc:
        print(f"投稿に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"投稿しました。post_id={post_id}")


if __name__ == "__main__":
    main()
