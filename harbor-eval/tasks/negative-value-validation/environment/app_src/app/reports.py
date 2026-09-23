from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MaintenanceLog, PartRestock


@dataclass
class CostByEquipment:
    equipment_id: int
    equipment_name: str
    total_cost: Decimal
    maintenance_count: int


@dataclass
class CostByMonth:
    month: str  # "2026-08"
    total_cost: Decimal


@dataclass
class MaintenanceCostReport:
    total_cost: Decimal
    by_equipment: list[CostByEquipment] = field(default_factory=list)
    by_month: list[CostByMonth] = field(default_factory=list)


def maintenance_cost_report(db: Session) -> MaintenanceCostReport:
    """What has keeping the fleet running actually cost, in parts.

    Reads PartUsed.unit_cost_at_time (the price snapshot from when the
    maintenance was logged), not Part.unit_cost -- so a price change today
    doesn't retroactively rewrite the cost of a six-month-old job.

    Aggregated in Python rather than with DB-side GROUP BY: this is a
    small-scale internal tool, and doing it here avoids SQL that only
    works on one of SQLite (dev) and Postgres (prod).
    """
    logs = db.execute(select(MaintenanceLog)).scalars().all()

    total = 0
    by_equipment: dict[int, CostByEquipment] = {}
    by_month: dict[str, Decimal] = defaultdict(lambda: 0)

    for log in logs:
        log_cost = sum((pu.quantity * pu.unit_cost_at_time for pu in log.parts_used), 0)
        total += log_cost

        eq = log.equipment
        entry = by_equipment.setdefault(
            eq.id,
            CostByEquipment(equipment_id=eq.id, equipment_name=eq.name, total_cost=0, maintenance_count=0),
        )
        entry.total_cost += log_cost
        entry.maintenance_count += 1

        month_key = log.performed_at.strftime("%Y-%m")
        by_month[month_key] += log_cost

    return MaintenanceCostReport(
        total_cost=total,
        by_equipment=sorted(by_equipment.values(), key=lambda c: c.total_cost, reverse=True),
        by_month=[CostByMonth(month=m, total_cost=c) for m, c in sorted(by_month.items())],
    )


@dataclass
class SpendByPart:
    part_id: int
    part_name: str
    total_cost: Decimal
    total_quantity: int


@dataclass
class SpendByMonth:
    month: str
    total_cost: Decimal


@dataclass
class PartsSpendReport:
    total_cost: Decimal
    by_part: list[SpendByPart] = field(default_factory=list)
    by_month: list[SpendByMonth] = field(default_factory=list)


def parts_spend_report(db: Session) -> PartsSpendReport:
    """What we've actually spent buying inventory -- the other half of the
    cost story. maintenance_cost_report is cost of parts consumed; this is
    cost of parts purchased. They're not the same number and don't need to
    match at any given point (you restock ahead of consumption)."""
    restocks = db.execute(select(PartRestock)).scalars().all()

    total = 0
    by_part: dict[int, SpendByPart] = {}
    by_month: dict[str, Decimal] = defaultdict(lambda: 0)

    for r in restocks:
        cost = r.quantity * r.unit_cost
        total += cost

        part = r.part
        entry = by_part.setdefault(
            part.id,
            SpendByPart(part_id=part.id, part_name=part.name, total_cost=0, total_quantity=0),
        )
        entry.total_cost += cost
        entry.total_quantity += r.quantity

        month_key = r.restocked_at.strftime("%Y-%m")
        by_month[month_key] += cost

    return PartsSpendReport(
        total_cost=total,
        by_part=sorted(by_part.values(), key=lambda s: s.total_cost, reverse=True),
        by_month=[SpendByMonth(month=m, total_cost=c) for m, c in sorted(by_month.items())],
    )
