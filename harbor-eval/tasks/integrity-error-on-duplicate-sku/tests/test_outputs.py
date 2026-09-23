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


def test_duplicate_sku_returns_clean_json_error_not_500():
    client = _client()
    body = {
        "name": "Wrench",
        "sku": "DUP1",
        "quantity_on_hand": 5,
        "reorder_threshold": 1,
        "unit_cost": "10.00",
    }
    r1 = client.post("/parts/", json=body)
    assert r1.status_code == 201, f"first create should succeed, got {r1.status_code}: {r1.text}"

    r2 = client.post("/parts/", json=body)
    assert r2.status_code != 500, (
        "duplicate SKU crashed with a raw 500 instead of a clean error response: " + r2.text
    )
    assert 400 <= r2.status_code < 500, (
        f"expected a 4xx client error for a duplicate SKU, got {r2.status_code}: {r2.text}"
    )
    # Must still be a well-formed JSON body, not an empty/broken response.
    data = r2.json()
    assert "detail" in data


def test_first_create_unaffected():
    client = _client()
    body = {
        "name": "Bolt",
        "sku": "UNIQUE1",
        "quantity_on_hand": 3,
        "reorder_threshold": 1,
        "unit_cost": "1.50",
    }
    r = client.post("/parts/", json=body)
    assert r.status_code == 201
