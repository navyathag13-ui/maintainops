from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ActivityEvent,
    ActivityEventType,
    Employee,
    Equipment,
    EquipmentLoan,
    MaintenanceLog,
    Part,
    PartRestock,
    PartUsed,
    Project,
    ProjectPartUsage,
)


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


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: int):
        self.project_id = project_id
        super().__init__(f"Project {project_id} not found")


class EmployeeNotFoundError(Exception):
    def __init__(self, employee_id: int):
        self.employee_id = employee_id
        super().__init__(f"Employee {employee_id} not found")


def log_activity(
    db: Session,
    event_type: ActivityEventType,
    description: str,
    *,
    project_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    equipment_id: Optional[int] = None,
    part_id: Optional[int] = None,
) -> ActivityEvent:
    """Every user-visible action in the app funnels through here so the
    activity feed is a real side effect of state changes, not a page that
    has to be told about them separately. `description` is written out in
    full at call time -- see ActivityEvent's docstring for why."""
    event = ActivityEvent(
        event_type=event_type,
        description=description,
        project_id=project_id,
        employee_id=employee_id,
        equipment_id=equipment_id,
        part_id=part_id,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def _maybe_log_low_stock_crossed(db: Session, part: Part, was_low_stock_before: bool) -> None:
    """Fires only on the transition into low stock, not on every
    already-low consumption -- otherwise using a part that's already
    below threshold would spam the feed with a duplicate event every time."""
    if not was_low_stock_before and is_part_low_stock(part):
        log_activity(
            db,
            ActivityEventType.LOW_STOCK_REACHED,
            f"{part.name} stock fell below its reorder threshold ({part.quantity_on_hand} remaining).",
            part_id=part.id,
        )


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
    # Lock parts in a canonical (id) order, not client-supplied order --
    # two concurrent multi-part logs referencing the same parts in opposite
    # order would otherwise each hold one lock and wait on the other,
    # deadlocking on Postgres instead of one of them simply waiting.
    for part_id in sorted({usage.part_id for usage in parts_used}):
        part = db.execute(
            select(Part).where(Part.id == part_id).with_for_update()
        ).scalar_one_or_none()
        if part is None:
            raise PartNotFoundError(part_id)
        parts_by_id[part_id] = part

    for usage in parts_used:
        part = parts_by_id[usage.part_id]
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
        was_low_stock = is_part_low_stock(part)
        part.quantity_on_hand -= usage.quantity
        log.parts_used.append(
            PartUsed(
                part_id=usage.part_id,
                quantity=usage.quantity,
                unit_cost_at_time=part.unit_cost,
            )
        )
        _maybe_log_low_stock_crossed(db, part, was_low_stock)

    equipment.last_maintenance_usage_hours = equipment.usage_hours

    log_activity(
        db,
        ActivityEventType.MAINTENANCE_LOGGED,
        f"Maintenance completed on {equipment.name}.",
        equipment_id=equipment.id,
    )

    db.add(log)
    db.flush()
    return log


def check_out_equipment(
    db: Session,
    equipment_id: int,
    project_id: int,
    borrower_employee_id: int,
    expected_return_at: datetime,
) -> EquipmentLoan:
    """Borrow a piece of equipment for a project. Rejects the checkout if
    it's already out to someone else -- one active (unreturned) loan per
    piece of equipment at a time. Moves current_location to the project,
    and counts this as one "use" toward the equipment's wear limit, if it
    has one.

    The manager isn't a parameter -- it's derived from the project's own
    `manager_id`, the same way the rest of this app derives state instead
    of asking the caller to repeat something already on record.

    `EquipmentLoan.project` / `manager_name` / `borrower_name` (plain
    strings) get populated here from the resolved records, so every
    existing reader of those columns keeps working unchanged -- the FK
    columns (`project_id`, `borrower_employee_id`) are the real link the
    new project/employee features are built on.
    """
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id).with_for_update()
    ).scalar_one_or_none()
    if equipment is None:
        raise EquipmentNotFoundError(equipment_id)

    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(project_id)

    borrower = db.get(Employee, borrower_employee_id)
    if borrower is None:
        raise EmployeeNotFoundError(borrower_employee_id)

    active_loan = db.execute(
        select(EquipmentLoan).where(
            EquipmentLoan.equipment_id == equipment_id,
            EquipmentLoan.returned_at.is_(None),
        )
    ).scalar_one_or_none()
    if active_loan is not None:
        raise EquipmentAlreadyCheckedOutError(equipment_id, active_loan.id)

    loan = EquipmentLoan(
        project=project.name,
        manager_name=project.manager.name if project.manager else "Unassigned",
        borrower_name=borrower.name,
        project_id=project.id,
        borrower_employee_id=borrower.id,
        checked_out_at=datetime.now(timezone.utc),
        expected_return_at=expected_return_at,
    )
    equipment.loans.append(loan)
    equipment.current_location = project.name
    equipment.usage_count += 1

    log_activity(
        db,
        ActivityEventType.EQUIPMENT_CHECKED_OUT,
        f"{borrower.name} checked out {equipment.name} for {project.name}.",
        project_id=project.id,
        employee_id=borrower.id,
        equipment_id=equipment.id,
    )

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

    # Lock the Equipment row too, not just the loan -- this function writes
    # current_location, the same column check_out_equipment locks Equipment
    # for before writing. Without this, the two functions' writes to that
    # column aren't serialized against each other.
    equipment = db.execute(
        select(Equipment).where(Equipment.id == loan.equipment_id).with_for_update()
    ).scalar_one()

    loan.returned_at = datetime.now(timezone.utc)
    equipment.current_location = equipment.location

    log_activity(
        db,
        ActivityEventType.EQUIPMENT_RETURNED,
        f"{loan.borrower_name} returned {equipment.name}.",
        project_id=loan.project_id,
        employee_id=loan.borrower_employee_id,
        equipment_id=equipment.id,
    )

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

    log_activity(
        db,
        ActivityEventType.PART_RESTOCKED,
        f"Received {quantity} x {part.name} from {supplier}.",
        part_id=part.id,
    )

    db.flush()
    return restock


def use_parts_on_project(
    db: Session,
    project_id: int,
    employee_id: Optional[int],
    parts_used: list[PartUsageInput],
    note: str = "",
) -> list[ProjectPartUsage]:
    """A project consuming parts directly (not through a maintenance job).
    Same shape as record_maintenance: validate everything, lock every part
    in canonical order, check all requested quantities against current
    stock before mutating any of them, and reject the whole request if one
    part is short -- no partial deduction.
    """
    seen_part_ids: set[int] = set()
    for usage in parts_used:
        if usage.quantity <= 0:
            raise InvalidQuantityError(usage.part_id, usage.quantity)
        if usage.part_id in seen_part_ids:
            raise DuplicatePartInRequestError(usage.part_id)
        seen_part_ids.add(usage.part_id)

    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(project_id)

    employee: Optional[Employee] = None
    if employee_id is not None:
        employee = db.get(Employee, employee_id)
        if employee is None:
            raise EmployeeNotFoundError(employee_id)

    parts_by_id: dict[int, Part] = {}
    shortfalls: list[StockShortfall] = []
    for part_id in sorted({usage.part_id for usage in parts_used}):
        part = db.execute(
            select(Part).where(Part.id == part_id).with_for_update()
        ).scalar_one_or_none()
        if part is None:
            raise PartNotFoundError(part_id)
        parts_by_id[part_id] = part

    for usage in parts_used:
        part = parts_by_id[usage.part_id]
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

    usages: list[ProjectPartUsage] = []
    now = datetime.now(timezone.utc)
    for usage in parts_used:
        part = parts_by_id[usage.part_id]
        was_low_stock = is_part_low_stock(part)
        part.quantity_on_hand -= usage.quantity

        record = ProjectPartUsage(
            project_id=project.id,
            part_id=part.id,
            employee_id=employee.id if employee else None,
            quantity=usage.quantity,
            unit_cost_at_time=part.unit_cost,
            note=note,
            used_at=now,
        )
        db.add(record)
        usages.append(record)

        who = f"{employee.name} used" if employee else f"{project.name} used"
        log_activity(
            db,
            ActivityEventType.PART_USED_ON_PROJECT,
            f"{who} {usage.quantity} {part.name} on {project.name}.",
            project_id=project.id,
            employee_id=employee.id if employee else None,
            part_id=part.id,
        )
        _maybe_log_low_stock_crossed(db, part, was_low_stock)

    db.flush()
    return usages
