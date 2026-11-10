"""Send low-stock alerts to a webhook (a Power Automate flow that posts to Teams).

Run once:          python -m app.notify --once
Run every 5 min:   python -m app.notify --every 300
Check the flow:    python -m app.notify --test   (one sample alert, no database)

The webhook URL comes from MAINTAINOPS_WEBHOOK_URL. It carries a signature
that lets anyone post to the flow, so it is never logged or printed.

Each LOW_STOCK_REACHED activity event is handled once:
  - sent     the webhook answered 2xx
  - failed   it didn't; the next run retries, up to MAX_ATTEMPTS
  - skipped  the part was restocked before the alert went out
  - stale    the event is older than MAX_AGE (e.g. the job was down for days)
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .logic import is_part_low_stock
from .models import ActivityEvent, ActivityEventType, Part, WebhookDelivery, WebhookDeliveryStatus

logger = logging.getLogger("maintainops.notify")

MAX_ATTEMPTS = 5
MAX_AGE = timedelta(hours=24)
TIMEOUT_S = 10

DONE = (WebhookDeliveryStatus.SENT, WebhookDeliveryStatus.SKIPPED, WebhookDeliveryStatus.STALE)

Post = Callable[..., httpx.Response]


def _utc(dt: datetime) -> datetime:
    # SQLite hands back naive datetimes; Postgres keeps the zone.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def pending_events(db: Session) -> list[ActivityEvent]:
    """Low-stock events not yet handled, oldest first, skipping ones out of retries."""
    handled = select(WebhookDelivery.event_id).where(
        (WebhookDelivery.status.in_(DONE)) | (WebhookDelivery.attempts >= MAX_ATTEMPTS)
    )
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.event_type == ActivityEventType.LOW_STOCK_REACHED)
            .where(ActivityEvent.id.not_in(handled))
            .order_by(ActivityEvent.occurred_at, ActivityEvent.id)
        )
    )


def build_payload(event: ActivityEvent) -> dict:
    """Plain fields for a custom flow, plus an Adaptive Card so Teams'
    'Post to a channel when a webhook request is received' template can
    show it with no extra mapping."""
    part = event.part
    text = (
        f"Low stock: {part.name} (SKU {part.sku}) has {part.quantity_on_hand} left; "
        f"reorder threshold is {part.reorder_threshold}."
    )
    return {
        "event_id": event.id,
        "part_id": part.id,
        "part_name": part.name,
        "sku": part.sku,
        "quantity_on_hand": part.quantity_on_hand,
        "reorder_threshold": part.reorder_threshold,
        "is_critical": part.is_critical,
        "occurred_at": _utc(event.occurred_at).isoformat(),
        "message": text,
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": "MaintainOps low-stock alert", "weight": "Bolder", "size": "Medium"},
                        {"type": "TextBlock", "text": text, "wrap": True},
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "On hand", "value": str(part.quantity_on_hand)},
                                {"title": "Reorder at", "value": str(part.reorder_threshold)},
                                {"title": "Critical", "value": "yes" if part.is_critical else "no"},
                            ],
                        },
                    ],
                },
            }
        ],
    }


def _record(db: Session, event: ActivityEvent, status: WebhookDeliveryStatus, error: str | None, attempted: bool) -> None:
    row = db.scalar(select(WebhookDelivery).where(WebhookDelivery.event_id == event.id))
    if row is None:
        row = WebhookDelivery(event_id=event.id, attempts=0)
        db.add(row)
    row.status = status
    row.last_error = error
    if attempted:
        row.attempts += 1
    row.updated_at = datetime.now(timezone.utc)
    db.commit()  # per event, so one bad send never undoes another's record


def send_pending(db: Session, url: str, post: Post = httpx.post, now: datetime | None = None) -> dict[str, int]:
    """Handle every pending event once. Returns a count per outcome."""
    now = now or datetime.now(timezone.utc)
    counts = {s.value: 0 for s in WebhookDeliveryStatus}
    for event in pending_events(db):
        if now - _utc(event.occurred_at) > MAX_AGE:
            _record(db, event, WebhookDeliveryStatus.STALE, None, attempted=False)
            counts["stale"] += 1
            continue
        if event.part is None or not is_part_low_stock(event.part):
            _record(db, event, WebhookDeliveryStatus.SKIPPED, None, attempted=False)
            counts["skipped"] += 1
            continue
        try:
            resp = post(url, json=build_payload(event), timeout=TIMEOUT_S)
            ok = 200 <= resp.status_code < 300
            error = None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.HTTPError as exc:
            ok, error = False, f"{type(exc).__name__}: {exc}"[:300]
        if ok:
            _record(db, event, WebhookDeliveryStatus.SENT, None, attempted=True)
            counts["sent"] += 1
            logger.info("Sent low-stock alert for event %s (%s)", event.id, event.part.name)
        else:
            _record(db, event, WebhookDeliveryStatus.FAILED, error, attempted=True)
            counts["failed"] += 1
            logger.warning("Low-stock alert for event %s failed: %s", event.id, error)
    return counts


def send_test_alert(url: str, post: Post = httpx.post) -> int:
    """POST one sample alert built from an unsaved part, without touching the database."""
    part = Part(id=0, name="Test part", sku="TEST-0", quantity_on_hand=2, reorder_threshold=5, is_critical=False)
    event = ActivityEvent(id=0, part=part, occurred_at=datetime.now(timezone.utc))
    try:
        resp = post(url, json=build_payload(event), timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        print(f"Could not reach the flow: {type(exc).__name__}", file=sys.stderr)
        return 1
    if 200 <= resp.status_code < 300:
        print(f"Flow accepted the test alert (HTTP {resp.status_code}). Check the Teams channel.")
        return 0
    print(f"Flow answered HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="handle pending alerts once and exit")
    mode.add_argument("--every", type=int, metavar="SECONDS", help="keep running, checking every SECONDS")
    mode.add_argument("--test", action="store_true", help="send one sample alert to check the flow is wired up")
    args = parser.parse_args(argv)

    url = os.getenv("MAINTAINOPS_WEBHOOK_URL")
    if not url and args.test and sys.stdin.isatty():
        url = getpass.getpass("Paste the flow URL (hidden): ").strip()
    if not url:
        print("Set MAINTAINOPS_WEBHOOK_URL to the flow's HTTP POST URL first.", file=sys.stderr)
        return 2

    if args.test:
        return send_test_alert(url)

    from .database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and this URL is a secret.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    while True:
        with SessionLocal() as db:
            counts = send_pending(db, url)
        logger.info("Run done: %s", counts)
        if args.once:
            return 0 if counts["failed"] == 0 else 1
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
