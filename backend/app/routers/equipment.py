from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import check_out_equipment, is_equipment_at_wear_limit, is_equipment_overdue
from ..models import Equipment
from ..schemas import (
    EquipmentCreate,
    EquipmentLoanCreate,
    EquipmentLoanRead,
    EquipmentRead,
    EquipmentUpdate,
    MaintenanceLogRead,
)

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _to_read(equipment: Equipment) -> EquipmentRead:
    return EquipmentRead(
        id=equipment.id,
        name=equipment.name,
        type=equipment.type,
        location=equipment.location,
        current_location=equipment.current_location,
        status=equipment.status,
        usage_hours=equipment.usage_hours,
        last_maintenance_usage_hours=equipment.last_maintenance_usage_hours,
        maintenance_interval_hours=equipment.maintenance_interval_hours,
        is_overdue=is_equipment_overdue(equipment),
        usage_count=equipment.usage_count,
        max_usage_count=equipment.max_usage_count,
        is_at_wear_limit=is_equipment_at_wear_limit(equipment),
        is_checked_out=any(loan.returned_at is None for loan in equipment.loans),
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
    # New equipment starts "at home": current_location mirrors location
    # until it's ever checked out.
    equipment = Equipment(**payload.model_dump(), current_location=payload.location)
    db.add(equipment)
    db.flush()
    return _to_read(equipment)


@router.patch("/{equipment_id}", response_model=EquipmentRead)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: Session = Depends(get_db)):
    # Locked, unlike the plain db.get() in _get_or_404 -- this mutates the
    # same row check_out_equipment/return_equipment lock before writing,
    # so an in-flight checkout/return shouldn't be clobbered by a concurrent
    # PATCH (or vice versa).
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id).with_for_update()
    ).scalar_one_or_none()
    if equipment is None:
        raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    db.flush()
    return _to_read(equipment)


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    if any(loan.returned_at is None for loan in equipment.loans):
        # Someone currently has this checked out. Deleting it would cascade
        # away that loan record -- the borrower's outstanding checkout
        # would just vanish with no error, warning, or record it ever
        # needs returning.
        raise HTTPException(
            status_code=409,
            detail=f"Equipment {equipment_id} is currently checked out and can't be deleted.",
        )
    db.delete(equipment)


@router.get("/{equipment_id}/history", response_model=list[MaintenanceLogRead])
def get_equipment_history(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    logs = sorted(equipment.maintenance_logs, key=lambda log: log.performed_at, reverse=True)
    return [MaintenanceLogRead.from_orm_with_parts(log) for log in logs]


@router.post("/{equipment_id}/checkout", response_model=EquipmentLoanRead, status_code=201)
def checkout_equipment(equipment_id: int, payload: EquipmentLoanCreate, db: Session = Depends(get_db)):
    loan = check_out_equipment(
        db,
        equipment_id=equipment_id,
        project=payload.project,
        manager_name=payload.manager_name,
        borrower_name=payload.borrower_name,
        expected_return_at=payload.expected_return_at,
    )
    return EquipmentLoanRead.from_orm_with_equipment_name(loan)


@router.get("/{equipment_id}/loans", response_model=list[EquipmentLoanRead])
def get_equipment_loans(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    loans = sorted(equipment.loans, key=lambda loan: loan.checked_out_at, reverse=True)
    return [EquipmentLoanRead.from_orm_with_equipment_name(loan) for loan in loans]
