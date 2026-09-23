from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityEvent, Employee
from ..schemas import (
    ActivityEventRead,
    EmployeeCreate,
    EmployeeDetailRead,
    EmployeeEquipmentRef,
    EmployeeProjectRef,
    EmployeeRead,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _get_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return employee


@router.get("", response_model=list[EmployeeRead])
def list_employees(db: Session = Depends(get_db)):
    return db.execute(select(Employee).order_by(Employee.name)).scalars().all()


@router.post("", response_model=EmployeeRead, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    employee = Employee(**payload.model_dump(), created_at=datetime.now(timezone.utc))
    db.add(employee)
    db.flush()
    return employee


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db)):
    employee = _get_or_404(db, employee_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    db.flush()
    return employee


@router.get("/{employee_id}", response_model=EmployeeDetailRead)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = _get_or_404(db, employee_id)

    current_projects = [
        EmployeeProjectRef(id=a.project.id, name=a.project.name, status=a.project.status)
        for a in employee.project_assignments
    ]

    borrowed_equipment = [
        EmployeeEquipmentRef(
            id=loan.equipment.id,
            name=loan.equipment.name,
            project_name=loan.project,
            expected_return_at=loan.expected_return_at,
        )
        for loan in employee.loans
        if loan.returned_at is None
    ]

    recent_activity = (
        db.execute(
            select(ActivityEvent)
            .where(ActivityEvent.employee_id == employee_id)
            .order_by(ActivityEvent.occurred_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    return EmployeeDetailRead(
        id=employee.id,
        name=employee.name,
        role=employee.role,
        active=employee.active,
        created_at=employee.created_at,
        current_projects=current_projects,
        borrowed_equipment=borrowed_equipment,
        recent_activity=[ActivityEventRead.from_orm_event(e) for e in recent_activity],
    )
