from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import is_equipment_overdue
from ..models import Equipment
from ..schemas import EquipmentCreate, EquipmentRead, EquipmentUpdate, MaintenanceLogRead

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _to_read(equipment: Equipment) -> EquipmentRead:
    return EquipmentRead(
        id=equipment.id,
        name=equipment.name,
        type=equipment.type,
        location=equipment.location,
        status=equipment.status,
        usage_hours=equipment.usage_hours,
        last_maintenance_usage_hours=equipment.last_maintenance_usage_hours,
        maintenance_interval_hours=equipment.maintenance_interval_hours,
        is_overdue=is_equipment_overdue(equipment),
    )


def _get_or_404(db: Session, equipment_id: int) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    return equipment


@router.get("", response_model=list[EquipmentRead])
def list_equipment(db: Session = Depends(get_db)):
    equipment = db.execute(select(Equipment).order_by(Equipment.id)).scalars().all()
    return [_to_read(e) for e in equipment]


@router.get("/{equipment_id}", response_model=EquipmentRead)
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    return _to_read(_get_or_404(db, equipment_id))


@router.post("", response_model=EquipmentRead, status_code=201)
def create_equipment(payload: EquipmentCreate, db: Session = Depends(get_db)):
    equipment = Equipment(**payload.model_dump())
    db.add(equipment)
    db.flush()
    return _to_read(equipment)


@router.patch("/{equipment_id}", response_model=EquipmentRead)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    db.flush()
    return _to_read(equipment)


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    db.delete(equipment)


@router.get("/{equipment_id}/history", response_model=list[MaintenanceLogRead])
def get_equipment_history(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    logs = sorted(equipment.maintenance_logs, key=lambda log: log.performed_at, reverse=True)
    return [MaintenanceLogRead.from_orm_with_parts(log) for log in logs]
