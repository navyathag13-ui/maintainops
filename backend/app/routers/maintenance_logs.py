from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import PartUsageInput, record_maintenance
from ..schemas import MaintenanceLogCreate, MaintenanceLogRead

router = APIRouter(prefix="/maintenance-logs", tags=["maintenance-logs"])


@router.post("", response_model=MaintenanceLogRead, status_code=201)
def create_maintenance_log(payload: MaintenanceLogCreate, db: Session = Depends(get_db)):
    log = record_maintenance(
        db,
        equipment_id=payload.equipment_id,
        performed_at=payload.performed_at or datetime.now(timezone.utc),
        description=payload.description,
        parts_used=[PartUsageInput(part_id=p.part_id, quantity=p.quantity) for p in payload.parts_used],
    )
    return MaintenanceLogRead.from_orm_with_parts(log)
