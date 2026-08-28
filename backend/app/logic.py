from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Equipment, EquipmentLoan, MaintenanceLog, Part, PartRestock, PartUsed


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


def is_equipment_at_wear_limit(equipment: Equipment) -> bool:
    """Some equipment is rated for a fixed number of uses rather than (or
    in addition to) hours -- e.g. a harness rated for 5 deployments. No
    limit set (max_usage_count is None) means this never applies."""
    if equipment.max_usage_count is None:
        return False
    return equipment.usage_count >= equipment.max_usage_count


def part_urgency(part: Part) -> Literal["none", "watch", "urgent"]:
    """"none" if stock is fine. Otherwise "urgent" for a part marked
    critical (work stops without it) and "watch" for everything else low
    -- can wait a few days for a restock."""
    if not is_part_low_stock(part):
        return "none"
    return "urgent" if part.is_critical else "watch"


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


class EquipmentAlreadyCheckedOutError(Exception):
    def __init__(self, equipment_id: int, active_loan_id: int):
        self.equipment_id = equipment_id
        self.active_loan_id = active_loan_id
        super().__init__(
            f"Equipment {equipment_id} is already checked out (loan {active_loan_id}) -- return it first"
        )


class LoanNotFoundError(Exception):
    def __init__(self, loan_id: int):
        self.loan_id = loan_id
        super().__init__(f"Loan {loan_id} not found")


class LoanAlreadyReturnedError(Exception):
    def __init__(self, loan_id: int):
        self.loan_id = loan_id
        super().__init__(f"Loan {loan_id} was already returned")


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
        log.parts_used.append(
            PartUsed(
                part_id=usage.part_id,
                quantity=usage.quantity,
                unit_cost_at_time=part.unit_cost,
            )
        )

    equipment.last_maintenance_usage_hours = equipment.usage_hours

    db.add(log)
    db.flush()
    return log


def check_out_equipment(
    db: Session,
    equipment_id: int,
    project: str,
    manager_name: str,
    borrower_name: str,
    expected_return_at: datetime,
) -> EquipmentLoan:
    """Borrow a piece of equipment. Rejects the checkout if it's already
    out to someone else -- one active (unreturned) loan per piece of
    equipment at a time. Moves current_location to the project, and counts
    this as one "use" toward the equipment's wear limit, if it has one.
    """
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id).with_for_update()
    ).scalar_one_or_none()
    if equipment is None:
        raise EquipmentNotFoundError(equipment_id)

    active_loan = db.execute(
        select(EquipmentLoan).where(
            EquipmentLoan.equipment_id == equipment_id,
            EquipmentLoan.returned_at.is_(None),
        )
    ).scalar_one_or_none()
    if active_loan is not None:
        raise EquipmentAlreadyCheckedOutError(equipment_id, active_loan.id)

    loan = EquipmentLoan(
        project=project,
        manager_name=manager_name,
        borrower_name=borrower_name,
        checked_out_at=datetime.now(timezone.utc),
        expected_return_at=expected_return_at,
    )
    equipment.loans.append(loan)
    equipment.current_location = project
    equipment.usage_count += 1

    db.flush()
    return loan


def return_equipment(db: Session, loan_id: int) -> EquipmentLoan:
    """Return a borrowed piece of equipment, moving it back to its home
    location."""
    loan = db.execute(
        select(EquipmentLoan).where(EquipmentLoan.id == loan_id).with_for_update()
    ).scalar_one_or_none()
    if loan is None:
        raise LoanNotFoundError(loan_id)
    if loan.returned_at is not None:
        raise LoanAlreadyReturnedError(loan_id)

    loan.returned_at = datetime.now(timezone.utc)
    loan.equipment.current_location = loan.equipment.location

    db.flush()
    return loan


def restock_part(
    db: Session,
    part_id: int,
    quantity: int,
    unit_cost,
    supplier: str,
    notes: str = "",
) -> PartRestock:
    """Receive a shipment: adds to stock and records what was actually paid.

    Part.unit_cost is updated to this shipment's price -- it's meant to
    reflect the current/latest price, used as the default for the next
    maintenance log's cost snapshot. Past MaintenanceLog cost snapshots
    (PartUsed.unit_cost_at_time) are untouched, since they already captured
    whatever the price was at the time.
    """
    if quantity <= 0:
        raise InvalidQuantityError(part_id, quantity)

    part = db.execute(
        select(Part).where(Part.id == part_id).with_for_update()
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError(part_id)

    restock = PartRestock(
        quantity=quantity,
        unit_cost=unit_cost,
        supplier=supplier,
        notes=notes,
        restocked_at=datetime.now(timezone.utc),
    )
    part.restocks.append(restock)
    part.quantity_on_hand += quantity
    part.unit_cost = unit_cost

    db.flush()
    return restock
