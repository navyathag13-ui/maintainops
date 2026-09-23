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


def test_deleting_checked_out_equipment_is_refused_and_loan_survives():
    client = _client()

    eq_id = client.post(
        "/equipment/",
        json={"name": "Drill", "type": "tool", "location": "bay1", "maintenance_interval_hours": "100"},
    ).json()["id"]
    emp_id = client.post("/employees/", json={"name": "Alice", "role": "technician"}).json()["id"]
    proj_id = client.post("/projects/", json={"name": "Site A"}).json()["id"]

    checkout = client.post(
        f"/equipment/{eq_id}/checkout",
        json={
            "project_id": proj_id,
            "borrower_employee_id": emp_id,
            "expected_return_at": "2026-12-01T00:00:00Z",
        },
    )
    assert checkout.status_code == 201, checkout.text

    loans_before = client.get("/equipment-loans").json()
    assert len(loans_before) == 1

    r = client.delete(f"/equipment/{eq_id}")
    assert 400 <= r.status_code < 500, (
        f"deleting checked-out equipment should be refused with a 4xx error, got {r.status_code}: {r.text}"
    )

    loans_after = client.get("/equipment-loans").json()
    assert len(loans_after) == 1, "the active loan record must not be destroyed by the refused delete"

    still_there = client.get(f"/equipment/{eq_id}")
    assert still_there.status_code == 200, "the equipment itself must not be deleted either"


def test_deleting_equipment_with_no_active_loan_still_works():
    client = _client()
    eq_id = client.post(
        "/equipment/",
        json={"name": "Sander", "type": "tool", "location": "bay2", "maintenance_interval_hours": "100"},
    ).json()["id"]

    r = client.delete(f"/equipment/{eq_id}")
    assert r.status_code == 204, r.text
