import re
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.logic import InsufficientStockError, PartUsageInput, record_maintenance


def _seeded_session():
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = Session(engine)

    locked_part_ids: list[int] = []

    @event.listens_for(db, "do_orm_execute")
    def _capture(orm_execute_state):
        stmt = orm_execute_state.statement
        if orm_execute_state.is_select and getattr(stmt, "_for_update_arg", None) is not None:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            if "FROM parts" in compiled:
                m = re.search(r"parts\.id = (\d+)", compiled)
                if m:
                    locked_part_ids.append(int(m.group(1)))

    db.add(models.Part(name="A", sku="LOCK-A", quantity_on_hand=10, reorder_threshold=1, unit_cost=1))
    db.add(models.Part(name="B", sku="LOCK-B", quantity_on_hand=10, reorder_threshold=1, unit_cost=1))
    db.add(
        models.Equipment(
            name="Eq", type="t", location="loc", current_location="loc", maintenance_interval_hours=100
        )
    )
    db.commit()

    return db, locked_part_ids


def test_parts_are_locked_in_canonical_order_not_client_supplied_order():
    """Regardless of the order the caller lists parts_used in, the rows
    must be locked in a fixed, deterministic order (e.g. sorted by id) so
    that two concurrent calls referencing the same parts in opposite
    request order can't each hold one lock and wait on the other."""
    db, locked_part_ids = _seeded_session()
    parts = db.query(models.Part).order_by(models.Part.id).all()
    higher_id, lower_id = parts[1].id, parts[0].id

    equipment = db.query(models.Equipment).first()
    usages = [
        PartUsageInput(part_id=higher_id, quantity=1),
        PartUsageInput(part_id=lower_id, quantity=1),
    ]

    record_maintenance(
        db,
        equipment_id=equipment.id,
        performed_at=datetime.now(timezone.utc),
        description="test",
        parts_used=usages,
    )
    db.commit()

    assert locked_part_ids == sorted(locked_part_ids), (
        f"Part rows were locked in order {locked_part_ids}, which does not match a canonical "
        f"(sorted) order. Client-supplied request order was [{higher_id}, {lower_id}] -- locking "
        "must not follow that order directly, or two concurrent requests referencing the same "
        "parts in opposite order can deadlock each other."
    )


def test_stock_shortfall_behavior_is_unchanged():
    """The fix must not alter record_maintenance's observable behavior --
    a shortfall on any part must still abort the whole log with no partial
    stock decrements."""
    db, _ = _seeded_session()
    parts = db.query(models.Part).order_by(models.Part.id).all()
    equipment = db.query(models.Equipment).first()

    usages = [
        PartUsageInput(part_id=parts[0].id, quantity=1),
        PartUsageInput(part_id=parts[1].id, quantity=999),  # exceeds stock
    ]

    with pytest.raises(InsufficientStockError):
        record_maintenance(
            db,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="test",
            parts_used=usages,
        )
    db.rollback()

    db.expire_all()
    refreshed = db.query(models.Part).order_by(models.Part.id).all()
    assert refreshed[0].quantity_on_hand == 10, "no partial stock decrement should happen on shortfall"
    assert refreshed[1].quantity_on_hand == 10
