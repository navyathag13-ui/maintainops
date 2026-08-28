import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EquipmentStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DOWN = "down"
    MAINTENANCE = "maintenance"


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Home/storage location -- where this equipment lives when nothing has
    # it checked out. `current_location` (below) is where it actually is
    # right now, and moves with checkout/return.
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    current_location: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[EquipmentStatus] = mapped_column(
        SAEnum(EquipmentStatus, name="equipment_status"),
        nullable=False,
        default=EquipmentStatus.OPERATIONAL,
    )
    # Numeric, not Float: the overdue check is an exact >= comparison, and
    # usage_hours accumulates from repeated updates -- float rounding drift
    # could eventually put equipment on the wrong side of the threshold.
    usage_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    last_maintenance_usage_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    maintenance_interval_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Wear-limit tracking: some equipment is only rated for a fixed number
    # of uses (each checkout counts as one), independent of the hour-based
    # maintenance interval above. max_usage_count is null for equipment
    # with no such limit -- most of the fleet.
    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)
    max_usage_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    maintenance_logs: Mapped[list["MaintenanceLog"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    loans: Mapped[list["EquipmentLoan"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    quantity_on_hand: Mapped[int] = mapped_column(nullable=False, default=0)
    reorder_threshold: Mapped[int] = mapped_column(nullable=False, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Manually set by whoever knows the part: does running out actually stop
    # work (safety gear, a part with no substitute), or can it wait a few
    # days for a restock? Drives urgency, not just the low-stock flag.
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    usages: Mapped[list["PartUsed"]] = relationship(back_populates="part")
    restocks: Mapped[list["PartRestock"]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    equipment: Mapped["Equipment"] = relationship(back_populates="maintenance_logs")
    parts_used: Mapped[list["PartUsed"]] = relationship(
        back_populates="maintenance_log", cascade="all, delete-orphan"
    )


class PartUsed(Base):
    __tablename__ = "parts_used"

    maintenance_log_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_logs.id"), primary_key=True
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # Snapshot of Part.unit_cost at the moment this maintenance was logged.
    # Cost reports read this, not the part's current price -- otherwise a
    # price change today would silently rewrite the cost of a job from six
    # months ago.
    unit_cost_at_time: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    maintenance_log: Mapped["MaintenanceLog"] = relationship(back_populates="parts_used")
    part: Mapped["Part"] = relationship(back_populates="usages")


class EquipmentLoan(Base):
    """One borrow/return cycle. `returned_at is None` means the loan is
    still active -- that's how we know a piece of equipment is currently
    checked out, without a separate boolean to keep in sync."""

    __tablename__ = "equipment_loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    # project/manager_name/borrower_name stay as plain strings -- every
    # existing read of a loan (reports, tests, display code) uses them, and
    # nothing about linking a loan to real Project/Employee records requires
    # breaking that. When a checkout goes through project_id/borrower_employee_id
    # (the only path the frontend uses now), these are auto-derived from the
    # linked records at creation time, not typed by hand. project_id and
    # borrower_employee_id are the actual source of truth for every
    # relational feature (a project's equipment list, an employee's borrowed
    # list, dashboard aggregation) -- the strings are display convenience.
    project: Mapped[str] = mapped_column(String(200), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(200), nullable=False)
    borrower_name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    borrower_employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    checked_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_return_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="loans")
    project_ref: Mapped[Optional["Project"]] = relationship(back_populates="loans")
    borrower: Mapped[Optional["Employee"]] = relationship(back_populates="loans")


class PartRestock(Base):
    """One inbound shipment. Stock only ever went down (consumed by
    maintenance) before this existed -- this is the other half of the
    inventory story: how it came back, when, from whom, and at what price.
    unit_cost here is what was actually paid for this shipment; Part.unit_cost
    is updated to match, so future maintenance cost snapshots reflect the
    latest price without rewriting history."""

    __tablename__ = "part_restocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    restocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    part: Mapped["Part"] = relationship(back_populates="restocks")


class EmployeeRole(str, enum.Enum):
    MANAGER = "manager"
    TECHNICIAN = "technician"
    EQUIPMENT_OPERATOR = "equipment_operator"
    SITE_WORKER = "site_worker"


class Employee(Base):
    """Not an HR system -- just enough of a record that managers, borrowers,
    and project teams can be picked from a real list instead of typed by
    hand. "Current project(s)" and "currently borrowed equipment" are never
    stored here: they're derived from ProjectEmployee assignments and active
    EquipmentLoan rows, same reasoning as Equipment.is_checked_out."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[EmployeeRole] = mapped_column(SAEnum(EmployeeRole, name="employee_role"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    loans: Mapped[list["EquipmentLoan"]] = relationship(back_populates="borrower")
    project_assignments: Mapped[list["ProjectEmployee"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    part_usages: Mapped[list["ProjectPartUsage"]] = relationship(back_populates="employee")
    managed_projects: Mapped[list["Project"]] = relationship(back_populates="manager")


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"), nullable=False, default=ProjectStatus.PLANNING
    )
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    manager: Mapped[Optional["Employee"]] = relationship(back_populates="managed_projects")
    loans: Mapped[list["EquipmentLoan"]] = relationship(back_populates="project_ref")
    team_assignments: Mapped[list["ProjectEmployee"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    part_usages: Mapped[list["ProjectPartUsage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectEmployee(Base):
    """Team staffing: this person is assigned to this project. Distinct from
    an EquipmentLoan's borrower_employee_id -- being on the team doesn't
    mean currently holding equipment, and vice versa (a manager can approve
    a checkout for someone off-roster without this app modeling that as a
    staffing decision)."""

    __tablename__ = "project_employees"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="team_assignments")
    employee: Mapped["Employee"] = relationship(back_populates="project_assignments")


class ProjectPartUsage(Base):
    """A project consuming parts directly -- separate from PartUsed
    (maintenance consumption) because the two happen for different reasons
    and are reported on separately (equipment upkeep cost vs. project
    material cost), even though the underlying mechanics (validate stock,
    decrement, snapshot the price) are the same shape."""

    __tablename__ = "project_part_usages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # Same principle as PartUsed.unit_cost_at_time: a price change next
    # month shouldn't rewrite what this project's material cost was today.
    unit_cost_at_time: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="part_usages")
    part: Mapped["Part"] = relationship()
    employee: Mapped[Optional["Employee"]] = relationship(back_populates="part_usages")


class ActivityEventType(str, enum.Enum):
    EQUIPMENT_CHECKED_OUT = "equipment_checked_out"
    EQUIPMENT_RETURNED = "equipment_returned"
    MAINTENANCE_LOGGED = "maintenance_logged"
    PART_USED_ON_PROJECT = "part_used_on_project"
    PART_RESTOCKED = "part_restocked"
    PROJECT_CREATED = "project_created"
    EMPLOYEE_ASSIGNED = "employee_assigned"
    LOW_STOCK_REACHED = "low_stock_reached"


class ActivityEvent(Base):
    """The global activity feed. `description` is a plain string frozen at
    creation time rather than assembled from the linked records on every
    read -- same reasoning as PartUsed.unit_cost_at_time: a feed is a
    historical log, and it shouldn't silently reword itself if an equipment
    or employee record is edited later. The FK columns exist so the feed can
    still link out to the current state of those records; the sentence
    itself is permanent."""

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[ActivityEventType] = mapped_column(
        SAEnum(ActivityEventType, name="activity_event_type"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parts.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Optional["Project"]] = relationship()
    employee: Mapped[Optional["Employee"]] = relationship()
    equipment: Mapped[Optional["Equipment"]] = relationship()
    part: Mapped[Optional["Part"]] = relationship()
