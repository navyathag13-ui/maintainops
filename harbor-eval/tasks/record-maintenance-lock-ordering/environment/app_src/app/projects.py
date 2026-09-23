"""Read-only project aggregation -- computed metrics derived from
EquipmentLoan/ProjectEmployee/ProjectPartUsage rows, never stored. Same
"logic.py mutates, this reads" split as reports.py. Shared between the
dashboard's active-projects section and the projects router's list/detail
views so the definition of "equipment count" etc. only lives in one place.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from .logic import is_equipment_overdue
from .models import Employee, Equipment, EquipmentLoan, Project, ProjectPartUsage

# A loan due back within this window counts as "due soon" on a project card
# and in the Dashboard's Due Soon section -- not configurable via the API,
# just a display threshold.
DUE_SOON_WINDOW = timedelta(days=3)


@dataclass
class ProjectSummary:
    id: int
    name: str
    status: str
    manager_id: Optional[int]
    manager_name: Optional[str]
    equipment_count: int
    parts_used_count: int
    worker_count: int
    due_back_soon_count: int
    maintenance_warning_count: int


@dataclass
class MaintenanceWarning:
    equipment_id: int
    equipment_name: str
    hours_overdue: Decimal


@dataclass
class ProjectDetail(ProjectSummary):
    code: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[object] = None
    expected_end_date: Optional[object] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    team: list[Employee] = field(default_factory=list)
    equipment_on_site: list[Equipment] = field(default_factory=list)
    parts_used: list[ProjectPartUsage] = field(default_factory=list)
    maintenance_warnings: list[MaintenanceWarning] = field(default_factory=list)


def _active_loans(project: Project) -> list[EquipmentLoan]:
    return [loan for loan in project.loans if loan.returned_at is None]


def as_aware_utc(value: datetime) -> datetime:
    """SQLite doesn't actually persist tzinfo through a DateTime(timezone=True)
    column -- a value written as UTC-aware comes back naive on read, even
    though Postgres (the real target) round-trips it correctly. Comparing a
    naive DB value against an aware `datetime.now(timezone.utc)` raises
    TypeError, so anything read back and compared against "now" goes through
    this first. A naive value is assumed UTC, since that's the only way
    anything in this app ever writes one."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def summarize_project(project: Project, now: Optional[datetime] = None) -> ProjectSummary:
    """Pure function over an already-loaded Project -- caller is
    responsible for eager-loading `loans` (+ their `equipment`),
    `part_usages`, `team_assignments`, and `manager`, or this silently
    triggers a lazy-load per relationship per project."""
    now = now or datetime.now(timezone.utc)
    active_loans = _active_loans(project)
    equipment_ids = {loan.equipment_id for loan in active_loans}
    return ProjectSummary(
        id=project.id,
        name=project.name,
        status=project.status.value,
        manager_id=project.manager_id,
        manager_name=project.manager.name if project.manager else None,
        equipment_count=len(equipment_ids),
        parts_used_count=len({usage.part_id for usage in project.part_usages}),
        worker_count=len(project.team_assignments),
        due_back_soon_count=sum(
            1 for loan in active_loans if as_aware_utc(loan.expected_return_at) <= now + DUE_SOON_WINDOW
        ),
        maintenance_warning_count=sum(
            1 for loan in active_loans if is_equipment_overdue(loan.equipment)
        ),
    )


def build_project_detail(project: Project, now: Optional[datetime] = None) -> ProjectDetail:
    now = now or datetime.now(timezone.utc)
    summary = summarize_project(project, now)
    active_loans = _active_loans(project)

    warnings = [
        MaintenanceWarning(
            equipment_id=loan.equipment.id,
            equipment_name=loan.equipment.name,
            hours_overdue=(
                (loan.equipment.usage_hours - loan.equipment.last_maintenance_usage_hours)
                - loan.equipment.maintenance_interval_hours
            ),
        )
        for loan in active_loans
        if is_equipment_overdue(loan.equipment)
    ]

    return ProjectDetail(
        **summary.__dict__,
        code=project.code,
        description=project.description,
        start_date=project.start_date,
        expected_end_date=project.expected_end_date,
        location=project.location,
        created_at=project.created_at,
        team=[a.employee for a in project.team_assignments],
        equipment_on_site=[loan.equipment for loan in active_loans],
        parts_used=list(project.part_usages),
        maintenance_warnings=warnings,
    )
