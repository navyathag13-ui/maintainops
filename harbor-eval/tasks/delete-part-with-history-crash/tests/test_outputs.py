import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


def _client() -> TestClient:
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=sa.pool.StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = TestSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=False)


def test_deleting_part_with_history_returns_clean_error_not_500():
    client = _client()

    part_id = client.post(
        "/parts/",
        json={"name": "Filter", "sku": "F1", "quantity_on_hand": 10, "reorder_threshold": 1, "unit_cost": "5.00"},
    ).json()["id"]
    eq_id = client.post(
        "/equipment/",
        json={"name": "Pump", "type": "pump", "location": "bay1", "maintenance_interval_hours": "100"},
    ).json()["id"]

    log = client.post(
        "/maintenance-logs",
        json={
            "equipment_id": eq_id,
            "performed_at": "2026-01-01T00:00:00Z",
            "description": "test",
            "parts_used": [{"part_id": part_id, "quantity": 1}],
        },
    )
    assert log.status_code == 201, log.text

    r = client.delete(f"/parts/{part_id}")
    assert r.status_code != 500, (
        "deleting a part with maintenance history crashed with a raw 500: " + r.text
    )
    assert 400 <= r.status_code < 500, (
        f"expected a 4xx client error, got {r.status_code}: {r.text}"
    )

    # And it must genuinely still exist -- not been silently deleted anyway.
    still_there = client.get(f"/parts/{part_id}")
    assert still_there.status_code == 200


def test_deleting_unused_part_still_works():
    client = _client()
    part_id = client.post(
        "/parts/",
        json={"name": "Gasket", "sku": "G1", "quantity_on_hand": 4, "reorder_threshold": 1, "unit_cost": "2.00"},
    ).json()["id"]

    r = client.delete(f"/parts/{part_id}")
    assert r.status_code == 204, r.text
