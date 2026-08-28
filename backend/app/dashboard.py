"""GET /dashboard/summary's aggregation -- one query per concern, eager
loading where the dashboard's own worst case (N active projects, each with
loans/parts/team) would otherwise be N+1. Unlike alerts.py/reports.py,
this endpoint gets hit on every page load, so the eager-loading investment
here is deliberate rather than the "small tool, don't bother" tradeoff used
elsewhere.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .logic import is_equipment_at_wear_limit, is_equipment_overdue, is_part_low_stock
from .models import ActivityEvent, Equipment, EquipmentLoan, Part, Project, ProjectStatus
from .projects import DUE_SOON_WINDOW, ProjectSummary, as_aware_utc, summarize_project


@dataclass
class LocationCount:
    location: str
    count: int


@dataclass
class DueSoonItem:
    loan_id: int
    equipment_id: int
    equipment_name: str
    project_name: str
    expected_return_at: datetime
    is_overdue_for_return: bool


@dataclass
class DashboardSummary:
    overdue_equipment: list[Equipment] = field(default_factory=list)
    low_stock_parts: list[Part] = field(default_factory=list)
    discard_recommended: list[Equipment] = field(default_factory=list)
    active_projects: list[ProjectSummary] = field(default_factory=list)
    equipment_by_location: list[LocationCount] = field(default_factory=list)
    due_soon: list[DueSoonItem] = field(default_factory=list)
    recent_activity: list[ActivityEvent] = field(default_factory=list)


def get_dashboard_summary(
    db: Session, activity_limit: int = 8, due_soon_limit: int = 6
) -> DashboardSummary:
    now = datetime.now(timezone.utc)

    equipment = db.execute(select(Equipment)).scalars().all()
    overdue_equipment = [e for e in equipment if is_equipment_overdue(e)]
    discard_recommended = [e for e in equipment if is_equipment_at_wear_limit(e)]

    location_counts: dict[str, int] = defaultdict(int)
    for e in equipment:
        location_counts[e.current_location] += 1
    equipment_by_location = sorted(
        (LocationCount(location=loc, count=count) for loc, count in location_counts.items()),
        key=lambda item: item.count,
        reverse=True,
    )

    parts = db.execute(select(Part)).scalars().all()
    low_stock_parts = [p for p in parts if is_part_low_stock(p)]

    active_loans = (
        db.execute(
            select(EquipmentLoan)
            .where(EquipmentLoan.returned_at.is_(None))
            .order_by(EquipmentLoan.expected_return_at.asc())
            .options(selectinload(EquipmentLoan.equipment))
            .limit(due_soon_limit)
        )
        .scalars()
        .all()
    )
    due_soon = [
        DueSoonItem(
            loan_id=loan.id,
            equipment_id=loan.equipment_id,
            equipment_name=loan.equipment.name,
            project_name=loan.project,
            expected_return_at=loan.expected_return_at,
            is_overdue_for_return=as_aware_utc(loan.expected_return_at) < now,
        )
        for loan in active_loans
    ]

    projects = (
        db.execute(
            select(Project)
            .where(Project.status == ProjectStatus.ACTIVE)
            .options(
                selectinload(Project.loans).selectinload(EquipmentLoan.equipment),
                selectinload(Project.part_usages),
                selectinload(Project.team_assignments),
                selectinload(Project.manager),
            )
            .order_by(Project.name)
        )
        .scalars()
        .all()
    )
    active_projects = [summarize_project(p, now) for p in projects]

    recent_activity = (
        db.execute(select(ActivityEvent).order_by(ActivityEvent.occurred_at.desc()).limit(activity_limit))
        .scalars()
        .all()
    )

    return DashboardSummary(
        overdue_equipment=overdue_equipment,
        low_stock_parts=low_stock_parts,
        discard_recommended=discard_recommended,
        active_projects=active_projects,
        equipment_by_location=equipment_by_location,
        due_soon=due_soon,
        recent_activity=list(recent_activity),
    )
