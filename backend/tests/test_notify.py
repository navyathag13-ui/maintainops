"""Low-stock webhook notifier (app/notify.py); a fake post stands in for Power Automate."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app import notify
from app.logic import restock_part
from app.models import ActivityEvent, ActivityEventType, Part, WebhookDelivery, WebhookDeliveryStatus

URL = "https://example.invalid/flow"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class FakePost:
    """Answers with the queued status codes (or raises a queued exception)."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes) or [202]
        self.calls = []

    def __call__(self, url, json, timeout):
        self.calls.append(json)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, text="nope" if outcome >= 300 else "")


def low_part(db, qty=2, threshold=5, name="Wood Screws", sku="WS-1"):
    part = Part(name=name, sku=sku, quantity_on_hand=qty, reorder_threshold=threshold, unit_cost=Decimal("1.00"))
    db.add(part)
    db.flush()
    return part


def low_event(db, part, at=NOW - timedelta(minutes=5)):
    event = ActivityEvent(
        event_type=ActivityEventType.LOW_STOCK_REACHED,
        description=f"{part.name} stock fell below its reorder threshold.",
        part_id=part.id,
        occurred_at=at,
    )
    db.add(event)
    db.commit()
    return event


def delivery(db, event):
    return db.query(WebhookDelivery).filter_by(event_id=event.id).one()


def test_sends_once_and_never_resends(db_session):
    event = low_event(db_session, low_part(db_session))
    post = FakePost(202)
    assert notify.send_pending(db_session, URL, post, NOW)["sent"] == 1
    assert notify.send_pending(db_session, URL, post, NOW)["sent"] == 0
    assert len(post.calls) == 1
    row = delivery(db_session, event)
    assert row.status == WebhookDeliveryStatus.SENT and row.attempts == 1


def test_payload_has_fields_and_a_teams_card(db_session):
    low_event(db_session, low_part(db_session, qty=2, threshold=5))
    post = FakePost(200)
    notify.send_pending(db_session, URL, post, NOW)
    body = post.calls[0]
    assert body["part_name"] == "Wood Screws" and body["quantity_on_hand"] == 2 and body["reorder_threshold"] == 5
    card = body["attachments"][0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert "2 left" in card["content"]["body"][1]["text"]


def test_only_low_stock_events_are_sent(db_session):
    part = low_part(db_session)
    db_session.add(ActivityEvent(event_type=ActivityEventType.PART_RESTOCKED, description="x",
                                 part_id=part.id, occurred_at=NOW))
    db_session.commit()
    post = FakePost(200)
    notify.send_pending(db_session, URL, post, NOW)
    assert post.calls == []


def test_failed_send_is_retried_next_run(db_session):
    event = low_event(db_session, low_part(db_session))
    notify.send_pending(db_session, URL, FakePost(500), NOW)
    row = delivery(db_session, event)
    assert row.status == WebhookDeliveryStatus.FAILED and row.attempts == 1 and "HTTP 500" in row.last_error
    assert notify.send_pending(db_session, URL, FakePost(202), NOW)["sent"] == 1
    row = delivery(db_session, event)
    assert row.status == WebhookDeliveryStatus.SENT and row.attempts == 2 and row.last_error is None


def test_network_error_is_recorded_not_raised(db_session):
    event = low_event(db_session, low_part(db_session))
    counts = notify.send_pending(db_session, URL, FakePost(httpx.ConnectTimeout("timed out")), NOW)
    assert counts["failed"] == 1
    assert "ConnectTimeout" in delivery(db_session, event).last_error


def test_gives_up_after_max_attempts(db_session):
    low_event(db_session, low_part(db_session))
    post = FakePost(503)
    for _ in range(notify.MAX_ATTEMPTS + 2):
        notify.send_pending(db_session, URL, post, NOW)
    assert len(post.calls) == notify.MAX_ATTEMPTS


def test_one_failure_does_not_block_the_next_alert(db_session):
    first = low_event(db_session, low_part(db_session, name="Screws", sku="S-1"))
    second = low_event(db_session, low_part(db_session, name="Gloves", sku="G-1"))
    counts = notify.send_pending(db_session, URL, FakePost(500, 202), NOW)
    assert counts["failed"] == 1 and counts["sent"] == 1
    assert delivery(db_session, first).status == WebhookDeliveryStatus.FAILED
    assert delivery(db_session, second).status == WebhookDeliveryStatus.SENT


def test_restocked_part_is_skipped(db_session):
    part = low_part(db_session, qty=2, threshold=5)
    event = low_event(db_session, part)
    restock_part(db_session, part.id, 10, Decimal("1.00"), "Acme")
    db_session.commit()
    post = FakePost(202)
    assert notify.send_pending(db_session, URL, post, NOW)["skipped"] == 1
    assert post.calls == [] and delivery(db_session, event).status == WebhookDeliveryStatus.SKIPPED


def test_old_event_is_marked_stale_not_sent(db_session):
    event = low_event(db_session, low_part(db_session), at=NOW - notify.MAX_AGE - timedelta(minutes=1))
    post = FakePost(202)
    assert notify.send_pending(db_session, URL, post, NOW)["stale"] == 1
    assert post.calls == [] and delivery(db_session, event).status == WebhookDeliveryStatus.STALE


def test_cli_refuses_to_run_without_a_url(monkeypatch, capsys):
    monkeypatch.delenv("MAINTAINOPS_WEBHOOK_URL", raising=False)
    assert notify.main(["--once"]) == 2
    assert "MAINTAINOPS_WEBHOOK_URL" in capsys.readouterr().err


def test_cli_never_logs_the_webhook_url(db_session, monkeypatch, caplog):
    secret = "https://prod.example.invalid/workflows/abc?sig=SECRET123"
    monkeypatch.setenv("MAINTAINOPS_WEBHOOK_URL", secret)
    low_event(db_session, low_part(db_session))
    bind = db_session.get_bind()

    import app.database as database
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(database, "engine", bind)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=bind, future=True))
    # a real httpx.post through a mock transport, so httpx's own logging runs
    transport = httpx.MockTransport(lambda request: httpx.Response(202))
    monkeypatch.setattr(notify.httpx, "post", lambda url, **kw: httpx.Client(transport=transport).post(url, **kw))
    monkeypatch.setattr(notify, "send_pending", lambda db, url, post=None, now=None: real_send(db, url, notify.httpx.post))

    with caplog.at_level("DEBUG"):
        assert notify.main(["--once"]) == 0
    assert "SECRET123" not in caplog.text


real_send = notify.send_pending


def test_test_mode_sends_one_sample_without_a_database():
    post = FakePost(202)
    assert notify.send_test_alert(URL, post) == 0
    assert post.calls[0]["part_name"] == "Test part"
    assert notify.send_test_alert(URL, FakePost(404)) == 1
