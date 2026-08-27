from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import is_equipment_overdue, is_part_low_stock
from ..models import Equipment, Part
from ..schemas import LowStockPartRead, OverdueEquipmentRead

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/overdue-maintenance", response_model=list[OverdueEquipmentRead])
def get_overdue_maintenance(db: Session = Depends(get_db)):
    equipment = db.execute(select(Equipment).order_by(Equipment.id)).scalars().all()
    overdue = [e for e in equipment if is_equipment_overdue(e)]
    return [
        OverdueEquipmentRead(
            id=e.id,
            name=e.name,
            location=e.location,
            usage_hours=e.usage_hours,
            last_maintenance_usage_hours=e.last_maintenance_usage_hours,
            maintenance_interval_hours=e.maintenance_interval_hours,
            hours_overdue=(e.usage_hours - e.last_maintenance_usage_hours) - e.maintenance_interval_hours,
        )
        for e in overdue
    ]


@router.get("/low-stock", response_model=list[LowStockPartRead])
def get_low_stock(db: Session = Depends(get_db)):
    parts = db.execute(select(Part).order_by(Part.id)).scalars().all()
    low_stock = [p for p in parts if is_part_low_stock(p)]
    return [
        LowStockPartRead(
            id=p.id,
            name=p.name,
            sku=p.sku,
            quantity_on_hand=p.quantity_on_hand,
            reorder_threshold=p.reorder_threshold,
        )
        for p in low_stock
    ]
