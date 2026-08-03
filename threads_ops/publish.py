"""Publish stage.

Only drafts that a human has approved (data/drafts/approved/) are ever
published. The default publisher is a mock that never makes a network
call -- it just records what *would* have been posted. A real publisher
against Meta's Threads Graph API is included for when credentials are
available, but it is opt-in (THREADS_OPS_PUBLISHER=real).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from . import config, storage
from .models import Draft, now_iso


@dataclass
class PublishResult:
    draft_id: str
    success: bool
    post_id: str | None
    detail: str


class Publisher(Protocol):
    name: str

    def publish(self, draft: Draft) -> PublishResult:
        ...


class MockPublisher:
    """Default, safe-by-construction publisher: no network calls."""

    name = "mock"

    def publish(self, draft: Draft) -> PublishResult:
        fake_id = f"mock_{draft.id}"
        return PublishResult(
            draft_id=draft.id,
            success=True,
            post_id=fake_id,
            detail="mock publish: no real API call was made",
        )


class ThreadsAPIPublisher:
    """Real publisher using Meta's Threads Graph API two-step publish flow.

    Requires THREADS_ACCESS_TOKEN and THREADS_USER_ID. See
    https://developers.facebook.com/docs/threads for setup: you need a
    Threads/Instagram professional account, a Meta developer app with the
    Threads API product, and a long-lived user access token with the
    threads_content_publish permission.
    """

    name = "threads_api"

    def __init__(self, access_token: str | None = None, user_id: str | None = None):
        self.access_token = access_token or config.THREADS_ACCESS_TOKEN
        self.user_id = user_id or config.THREADS_USER_ID
        if not self.access_token or not self.user_id:
            raise RuntimeError(
                "THREADS_ACCESS_TOKEN and THREADS_USER_ID must be set to use the real publisher"
            )

    def publish(self, draft: Draft) -> PublishResult:
        import requests

        base = config.THREADS_API_BASE
        try:
            create_resp = requests.post(
                f"{base}/{self.user_id}/threads",
                data={
                    "media_type": "TEXT",
                    "text": draft.text,
                    "access_token": self.access_token,
                },
                timeout=30,
            )
            create_resp.raise_for_status()
            creation_id = create_resp.json()["id"]

            publish_resp = requests.post(
                f"{base}/{self.user_id}/threads_publish",
                data={"creation_id": creation_id, "access_token": self.access_token},
                timeout=30,
            )
            publish_resp.raise_for_status()
            post_id = publish_resp.json().get("id")
            return PublishResult(draft.id, True, post_id, "published via Threads API")
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
            return PublishResult(draft.id, False, None, f"publish failed: {exc}")


def get_default_publisher() -> Publisher:
    if config.PUBLISHER_MODE == "real":
        return ThreadsAPIPublisher()
    return MockPublisher()


def publish_approved(
    publisher: Publisher | None = None,
    approved_dir=None,
    posted_dir=None,
    history_file=None,
    now: datetime | None = None,
) -> list[PublishResult]:
    """Publish every approved draft that is due.

    Drafts with a `scheduled_at` in the future are left untouched in
    approved/ so a later run (e.g. a daily cron) picks them up once their
    time comes -- this is what lets a week's worth of drafts, approved all
    at once, actually go out 6-a-day instead of all at once.
    """
    publisher = publisher or get_default_publisher()
    approved_dir = approved_dir or config.APPROVED_DIR
    posted_dir = posted_dir or config.POSTED_DIR
    history_file = history_file or config.HISTORY_FILE
    now = now or datetime.now(timezone.utc)

    results = []
    for path in storage.list_json_files(approved_dir):
        draft = Draft.from_dict(storage.read_json(path))

        if draft.scheduled_at and datetime.fromisoformat(draft.scheduled_at) > now:
            continue  # not due yet; stays in approved/ for a later publish run

        result = publisher.publish(draft)
        results.append(result)

        storage.append_jsonl(
            history_file,
            {
                "draft_id": draft.id,
                "topic": draft.topic,
                "publisher": publisher.name,
                "success": result.success,
                "post_id": result.post_id,
                "detail": result.detail,
                "published_at": now_iso(),
            },
        )

        if result.success:
            draft.status = "posted"
            storage.write_json(posted_dir / f"{draft.id}.json", draft.to_dict())
            path.unlink()
        # On failure the draft stays in approved/ so it can be retried.

    return results
