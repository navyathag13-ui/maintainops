from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..reports import maintenance_cost_report, parts_spend_report
from ..schemas import MaintenanceCostReportRead, PartsSpendReportRead

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/maintenance-cost", response_model=MaintenanceCostReportRead)
def get_maintenance_cost_report(db: Session = Depends(get_db)):
    report = maintenance_cost_report(db)
    return MaintenanceCostReportRead(
        total_cost=report.total_cost,
        by_equipment=[
            {
                "equipment_id": e.equipment_id,
                "equipment_name": e.equipment_name,
                "total_cost": e.total_cost,
                "maintenance_count": e.maintenance_count,
            }
            for e in report.by_equipment
        ],
        by_month=[{"month": m.month, "total_cost": m.total_cost} for m in report.by_month],
    )


@router.get("/parts-spend", response_model=PartsSpendReportRead)
def get_parts_spend_report(db: Session = Depends(get_db)):
    report = parts_spend_report(db)
    return PartsSpendReportRead(
        total_cost=report.total_cost,
        by_part=[
            {
                "part_id": p.part_id,
                "part_name": p.part_name,
                "total_cost": p.total_cost,
                "total_quantity": p.total_quantity,
            }
            for p in report.by_part
        ],
        by_month=[{"month": m.month, "total_cost": m.total_cost} for m in report.by_month],
    )
