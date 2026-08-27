from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Equipment, MaintenanceLog, Part, PartUsed


def is_equipment_overdue(equipment: Equipment) -> bool:
    """Usage-hours based, per spec: not calendar time.

    Overdue once the hours run since the last service meet or exceed the
    configured interval.
    """
    hours_since_service = equipment.usage_hours - equipment.last_maintenance_usage_hours
    return hours_since_service >= equipment.maintenance_interval_hours


def is_part_low_stock(part: Part) -> bool:
    """At-or-below the reorder threshold counts as low stock."""
    return part.quantity_on_hand <= part.reorder_threshold


@dataclass
class PartUsageInput:
    part_id: int
    quantity: int


@dataclass
class StockShortfall:
    part_id: int
    requested: int
    available: int


class EquipmentNotFoundError(Exception):
    def __init__(self, equipment_id: int):
        self.equipment_id = equipment_id
        super().__init__(f"Equipment {equipment_id} not found")


class PartNotFoundError(Exception):
    def __init__(self, part_id: int):
        self.part_id = part_id
        super().__init__(f"Part {part_id} not found")


class InvalidQuantityError(Exception):
    def __init__(self, part_id: int, quantity: int):
        self.part_id = part_id
        self.quantity = quantity
        super().__init__(f"Quantity for part {part_id} must be positive, got {quantity}")


class DuplicatePartInRequestError(Exception):
    def __init__(self, part_id: int):
        self.part_id = part_id
        super().__init__(f"Part {part_id} appears more than once in parts_used")


class InsufficientStockError(Exception):
    def __init__(self, shortfalls: list[StockShortfall]):
        self.shortfalls = shortfalls
        detail = ", ".join(
            f"part {s.part_id} (requested {s.requested}, available {s.available})"
            for s in shortfalls
        )
        super().__init__(f"Insufficient stock for: {detail}")


def record_maintenance(
    db: Session,
    equipment_id: int,
    performed_at: datetime,
    description: str,
    parts_used: list[PartUsageInput],
) -> MaintenanceLog:
    """Create a maintenance log, consume parts, and reset the equipment's
    maintenance baseline.

    Every part is checked against current stock before anything is mutated,
    so a shortfall on any single part aborts the whole log with no partial
    stock decrements. This function does not commit -- the caller (the API
    route) owns the transaction boundary and decides when to commit/rollback.

    Part rows are loaded with SELECT ... FOR UPDATE so two concurrent
    maintenance logs against the same part can't both pass the stock check
    before either commits -- the second waits for the first transaction to
    finish, then re-reads the now-current quantity. (No-op on SQLite, which
    has no row-level locking; this matters for the real Postgres target.)
    """
    # Validate the request shape before touching the database at all.
    seen_part_ids: set[int] = set()
    for usage in parts_used:
        if usage.quantity <= 0:
            raise InvalidQuantityError(usage.part_id, usage.quantity)
        if usage.part_id in seen_part_ids:
            raise DuplicatePartInRequestError(usage.part_id)
        seen_part_ids.add(usage.part_id)

    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id).with_for_update()
    ).scalar_one_or_none()
    if equipment is None:
        raise EquipmentNotFoundError(equipment_id)

    parts_by_id: dict[int, Part] = {}
    shortfalls: list[StockShortfall] = []
    for usage in parts_used:
        part = db.execute(
            select(Part).where(Part.id == usage.part_id).with_for_update()
        ).scalar_one_or_none()
        if part is None:
            raise PartNotFoundError(usage.part_id)
        parts_by_id[usage.part_id] = part
        if part.quantity_on_hand < usage.quantity:
            shortfalls.append(
                StockShortfall(
                    part_id=usage.part_id,
                    requested=usage.quantity,
                    available=part.quantity_on_hand,
                )
            )

    if shortfalls:
        raise InsufficientStockError(shortfalls)

    log = MaintenanceLog(
        performed_at=performed_at,
        description=description,
    )
    equipment.maintenance_logs.append(log)

    for usage in parts_used:
        part = parts_by_id[usage.part_id]
        part.quantity_on_hand -= usage.quantity
        log.parts_used.append(PartUsed(part_id=usage.part_id, quantity=usage.quantity))

    equipment.last_maintenance_usage_hours = equipment.usage_hours

    db.add(log)
    db.flush()
    return log
