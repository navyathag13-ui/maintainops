from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..logic import return_equipment
from ..models import EquipmentLoan
from ..schemas import EquipmentLoanRead

router = APIRouter(prefix="/equipment-loans", tags=["equipment-loans"])


@router.get("", response_model=list[EquipmentLoanRead])
def list_equipment_loans(
    active: Optional[bool] = Query(
        None, description="true = only currently checked-out equipment, false = only returned"
    ),
    db: Session = Depends(get_db),
):
    stmt = select(EquipmentLoan)
    if active is True:
        stmt = stmt.where(EquipmentLoan.returned_at.is_(None))
    elif active is False:
        stmt = stmt.where(EquipmentLoan.returned_at.is_not(None))
    stmt = stmt.order_by(EquipmentLoan.checked_out_at.desc())
    loans = db.execute(stmt).scalars().all()
    return [EquipmentLoanRead.from_orm_with_equipment_name(loan) for loan in loans]


@router.post("/{loan_id}/return", response_model=EquipmentLoanRead)
def return_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = return_equipment(db, loan_id)
    return EquipmentLoanRead.from_orm_with_equipment_name(loan)
