"""Real-Postgres check for the record_maintenance lock-ordering bug.

Two concurrent transactions log maintenance using the same two parts in
OPPOSITE order. A short delay after each Part row lock forces the interleaving
that deadlocks when locks are taken in client-supplied order.

Usage: PYTHONPATH=<app_src dir> python postgres_deadlock_check.py <postgres url>
"""
import sys, threading, time
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.database import Base
from app import models
from app.logic import record_maintenance, PartUsageInput

engine = sa.create_engine(sys.argv[1], future=True)
Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
with Session(engine) as s:
    s.add_all([models.Part(name="A", sku="A", quantity_on_hand=50, reorder_threshold=1, unit_cost=1),
               models.Part(name="B", sku="B", quantity_on_hand=50, reorder_threshold=1, unit_cost=1)]
              + [models.Equipment(name=f"E{i}", type="t", location="l", current_location="l",
                                  maintenance_interval_hours=100) for i in (1, 2)])
    s.commit()

@event.listens_for(engine, "after_cursor_execute")
def slow_after_part_lock(conn, cursor, statement, params, context, executemany):
    if "FROM parts" in statement and "FOR UPDATE" in statement:
        time.sleep(1.0)

results = {}
def run(name, equipment_id, order):
    with Session(engine) as s:
        try:
            record_maintenance(s, equipment_id, datetime.now(timezone.utc), name,
                               [PartUsageInput(part_id=p, quantity=1) for p in order])
            s.commit(); results[name] = "OK"
        except Exception as e:
            s.rollback(); results[name] = f"{type(e).__name__}: {str(getattr(e, 'orig', e)).splitlines()[0]}"

t1 = threading.Thread(target=run, args=("T1", 1, [1, 2]))
t2 = threading.Thread(target=run, args=("T2", 2, [2, 1]))
t1.start(); t2.start(); t1.join(); t2.join()
print(results)
print("DEADLOCK" if any("eadlock" in v for v in results.values()) else "NO DEADLOCK")
