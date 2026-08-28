from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import is_part_low_stock, part_urgency, restock_part
from ..models import Part
from ..schemas import PartCreate, PartRead, PartRestockCreate, PartRestockRead, PartUpdate

router = APIRouter(prefix="/parts", tags=["parts"])


def _to_read(part: Part) -> PartRead:
    return PartRead(
        id=part.id,
        name=part.name,
        sku=part.sku,
        quantity_on_hand=part.quantity_on_hand,
        reorder_threshold=part.reorder_threshold,
        unit_cost=part.unit_cost,
        is_critical=part.is_critical,
        is_low_stock=is_part_low_stock(part),
        urgency=part_urgency(part),
    )


def _get_or_404(db: Session, part_id: int) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"Part {part_id} not found")
    return part


@router.get("", response_model=list[PartRead])
def list_parts(db: Session = Depends(get_db)):
    parts = db.execute(select(Part).order_by(Part.id)).scalars().all()
    return [_to_read(p) for p in parts]


@router.get("/{part_id}", response_model=PartRead)
def get_part(part_id: int, db: Session = Depends(get_db)):
    return _to_read(_get_or_404(db, part_id))


@router.post("", response_model=PartRead, status_code=201)
def create_part(payload: PartCreate, db: Session = Depends(get_db)):
    part = Part(**payload.model_dump())
    db.add(part)
    db.flush()
    return _to_read(part)


@router.patch("/{part_id}", response_model=PartRead)
def update_part(part_id: int, payload: PartUpdate, db: Session = Depends(get_db)):
    part = _get_or_404(db, part_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    db.flush()
    return _to_read(part)


@router.delete("/{part_id}", status_code=204)
def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = _get_or_404(db, part_id)
    db.delete(part)


@router.post("/{part_id}/restock", response_model=PartRestockRead, status_code=201)
def restock(part_id: int, payload: PartRestockCreate, db: Session = Depends(get_db)):
    restock = restock_part(
        db,
        part_id=part_id,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        supplier=payload.supplier,
        notes=payload.notes,
    )
    return PartRestockRead.from_orm_with_part_name(restock)


@router.get("/{part_id}/restocks", response_model=list[PartRestockRead])
def get_restocks(part_id: int, db: Session = Depends(get_db)):
    part = _get_or_404(db, part_id)
    restocks = sorted(part.restocks, key=lambda r: r.restocked_at, reverse=True)
    return [PartRestockRead.from_orm_with_part_name(r) for r in restocks]
