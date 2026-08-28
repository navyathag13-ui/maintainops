from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..logic import (
    ActivityEventType,
    PartUsageInput,
    is_equipment_overdue,
    log_activity,
    use_parts_on_project,
)
from ..models import ActivityEvent, Employee, EquipmentLoan, Project, ProjectEmployee, ProjectPartUsage
from ..projects import build_project_detail, summarize_project
from ..schemas import (
    ActivityEventRead,
    MaintenanceWarningRead,
    ProjectCreate,
    ProjectDetailRead,
    ProjectEmployeeCreate,
    ProjectEquipmentRef,
    ProjectPartUsageCreate,
    ProjectPartUsageRead,
    ProjectSummaryRead,
    ProjectTeamMemberRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])

_DETAIL_OPTIONS = (
    selectinload(Project.loans).selectinload(EquipmentLoan.equipment),
    selectinload(Project.part_usages).selectinload(ProjectPartUsage.part),
    selectinload(Project.part_usages).selectinload(ProjectPartUsage.employee),
    selectinload(Project.team_assignments).selectinload(ProjectEmployee.employee),
    selectinload(Project.manager),
)


def _get_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _get_with_relations_or_404(db: Session, project_id: int) -> Project:
    project = db.execute(
        select(Project).where(Project.id == project_id).options(*_DETAIL_OPTIONS)
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _to_detail_read(project: Project) -> ProjectDetailRead:
    detail = build_project_detail(project)
    return ProjectDetailRead(
        **{k: v for k, v in detail.__dict__.items() if k not in ("team", "equipment_on_site", "parts_used", "maintenance_warnings")},
        team=[ProjectTeamMemberRead(id=e.id, name=e.name, role=e.role) for e in detail.team],
        equipment_on_site=[
            ProjectEquipmentRef(
                id=eq.id,
                name=eq.name,
                type=eq.type,
                is_overdue=is_equipment_overdue(eq),
                current_location=eq.current_location,
            )
            for eq in detail.equipment_on_site
        ],
        parts_used=[ProjectPartUsageRead.from_orm_usage(u) for u in detail.parts_used],
        maintenance_warnings=[
            MaintenanceWarningRead(
                equipment_id=w.equipment_id, equipment_name=w.equipment_name, hours_overdue=w.hours_overdue
            )
            for w in detail.maintenance_warnings
        ],
    )


@router.get("", response_model=list[ProjectSummaryRead])
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.execute(select(Project).options(*_DETAIL_OPTIONS).order_by(Project.name))
        .scalars()
        .all()
    )
    return [ProjectSummaryRead(**summarize_project(p).__dict__) for p in projects]


@router.post("", response_model=ProjectSummaryRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump(), created_at=datetime.now(timezone.utc))
    db.add(project)
    db.flush()
    log_activity(
        db,
        ActivityEventType.PROJECT_CREATED,
        f"Project {project.name} created.",
        project_id=project.id,
    )
    db.flush()
    return ProjectSummaryRead(
        **summarize_project(project).__dict__
    )


@router.get("/{project_id}", response_model=ProjectDetailRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = _get_with_relations_or_404(db, project_id)
    return _to_detail_read(project)


@router.patch("/{project_id}", response_model=ProjectDetailRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = _get_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.flush()
    return _to_detail_read(_get_with_relations_or_404(db, project_id))


@router.get("/{project_id}/activity", response_model=list[ActivityEventRead])
def get_project_activity(project_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, project_id)
    events = (
        db.execute(
            select(ActivityEvent)
            .where(ActivityEvent.project_id == project_id)
            .order_by(ActivityEvent.occurred_at.desc())
        )
        .scalars()
        .all()
    )
    return [ActivityEventRead.from_orm_event(e) for e in events]


@router.post("/{project_id}/employees", status_code=201)
def assign_employee(project_id: int, payload: ProjectEmployeeCreate, db: Session = Depends(get_db)):
    project = _get_or_404(db, project_id)
    employee = db.get(Employee, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {payload.employee_id} not found")

    # Composite PK on (project_id, employee_id) rejects a duplicate
    # assignment at the DB level -- the generic IntegrityError handler
    # turns that into a clean 409, same pattern as everywhere else a
    # composite key guards against a duplicate.
    assignment = ProjectEmployee(
        project_id=project.id, employee_id=employee.id, assigned_at=datetime.now(timezone.utc)
    )
    db.add(assignment)
    log_activity(
        db,
        ActivityEventType.EMPLOYEE_ASSIGNED,
        f"{employee.name} assigned to {project.name}.",
        project_id=project.id,
        employee_id=employee.id,
    )
    db.flush()
    return {"project_id": project.id, "employee_id": employee.id}


@router.post("/{project_id}/parts-usage", response_model=list[ProjectPartUsageRead], status_code=201)
def use_parts(project_id: int, payload: ProjectPartUsageCreate, db: Session = Depends(get_db)):
    usages = use_parts_on_project(
        db,
        project_id=project_id,
        employee_id=payload.employee_id,
        parts_used=[PartUsageInput(part_id=p.part_id, quantity=p.quantity) for p in payload.parts_used],
        note=payload.note,
    )
    return [ProjectPartUsageRead.from_orm_usage(u) for u in usages]
