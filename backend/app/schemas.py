from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import ActivityEventType, EmployeeRole, EquipmentStatus, ProjectStatus

# --- Equipment ---------------------------------------------------------------


class EquipmentBase(BaseModel):
    name: str
    type: str
    location: str
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    usage_hours: Decimal = Field(default=Decimal("0"), ge=0)
    maintenance_interval_hours: Decimal = Field(gt=0)
    # None = no wear limit, which is most equipment. Set only for gear
    # that's rated for a fixed number of uses.
    max_usage_count: Optional[int] = Field(default=None, gt=0)


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    current_location: Optional[str] = None
    status: Optional[EquipmentStatus] = None
    usage_hours: Optional[Decimal] = Field(default=None, ge=0)
    maintenance_interval_hours: Optional[Decimal] = Field(default=None, gt=0)
    max_usage_count: Optional[int] = Field(default=None, gt=0)


class EquipmentRead(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_location: str
    last_maintenance_usage_hours: Decimal
    is_overdue: bool
    usage_count: int
    is_at_wear_limit: bool
    is_checked_out: bool


# --- Parts ---------------------------------------------------------------


class PartBase(BaseModel):
    name: str
    sku: str
    quantity_on_hand: int = Field(default=0, ge=0)
    reorder_threshold: int = Field(default=0, ge=0)
    unit_cost: Decimal = Field(ge=0)
    # Does running out actually stop work? Drives urgency, set by whoever
    # knows the part -- not inferred from usage data we don't track.
    is_critical: bool = False


class PartCreate(PartBase):
    pass


class PartUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    quantity_on_hand: Optional[int] = Field(default=None, ge=0)
    reorder_threshold: Optional[int] = Field(default=None, ge=0)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    is_critical: Optional[bool] = None


class PartRead(PartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_low_stock: bool
    urgency: str  # "none" | "watch" | "urgent"


# --- Part restocks ---------------------------------------------------------------


class PartRestockCreate(BaseModel):
    quantity: int = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    supplier: str
    notes: str = ""


class PartRestockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    part_name: Optional[str] = None
    quantity: int
    unit_cost: Decimal
    supplier: Optional[str] = None
    notes: Optional[str] = None
    restocked_at: datetime

    @classmethod
    def from_orm_with_part_name(cls, restock) -> "PartRestockRead":
        return cls(
            id=restock.id,
            part_id=restock.part_id,
            part_name=restock.part.name if restock.part else None,
            quantity=restock.quantity,
            unit_cost=restock.unit_cost,
            supplier=restock.supplier,
            notes=restock.notes,
            restocked_at=restock.restocked_at,
        )


# --- Maintenance logs ---------------------------------------------------------------


class PartUsageIn(BaseModel):
    part_id: int
    quantity: int = Field(gt=0)


class PartUsedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    part_id: int
    quantity: int
    part_name: Optional[str] = None
    unit_cost_at_time: Decimal

    @classmethod
    def from_orm_with_part_name(cls, part_used) -> "PartUsedRead":
        return cls(
            part_id=part_used.part_id,
            quantity=part_used.quantity,
            part_name=part_used.part.name if part_used.part else None,
            unit_cost_at_time=part_used.unit_cost_at_time,
        )


class MaintenanceLogCreate(BaseModel):
    equipment_id: int
    performed_at: Optional[datetime] = None
    description: str
    parts_used: list[PartUsageIn] = []


class MaintenanceLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    performed_at: datetime
    description: str
    parts_used: list[PartUsedRead]

    @classmethod
    def from_orm_with_parts(cls, log) -> "MaintenanceLogRead":
        return cls(
            id=log.id,
            equipment_id=log.equipment_id,
            performed_at=log.performed_at,
            description=log.description,
            parts_used=[PartUsedRead.from_orm_with_part_name(pu) for pu in log.parts_used],
        )


# --- Equipment loans (borrow / return) ---------------------------------------


class EquipmentLoanCreate(BaseModel):
    project_id: int
    borrower_employee_id: int
    expected_return_at: datetime


class EquipmentLoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    project: str
    project_id: Optional[int] = None
    manager_name: str
    borrower_name: str
    borrower_employee_id: Optional[int] = None
    checked_out_at: datetime
    expected_return_at: datetime
    returned_at: Optional[datetime] = None

    @classmethod
    def from_orm_with_equipment_name(cls, loan) -> "EquipmentLoanRead":
        return cls(
            id=loan.id,
            equipment_id=loan.equipment_id,
            equipment_name=loan.equipment.name if loan.equipment else None,
            project=loan.project,
            project_id=loan.project_id,
            manager_name=loan.manager_name,
            borrower_name=loan.borrower_name,
            borrower_employee_id=loan.borrower_employee_id,
            checked_out_at=loan.checked_out_at,
            expected_return_at=loan.expected_return_at,
            returned_at=loan.returned_at,
        )


# --- Alerts ---------------------------------------------------------------


class OverdueEquipmentRead(BaseModel):
    id: int
    name: str
    location: str
    usage_hours: Decimal
    last_maintenance_usage_hours: Decimal
    maintenance_interval_hours: Decimal
    hours_overdue: Decimal


class LowStockPartRead(BaseModel):
    id: int
    name: str
    sku: str
    quantity_on_hand: int
    reorder_threshold: int
    is_critical: bool
    urgency: str  # "watch" | "urgent"


class WearLimitReachedRead(BaseModel):
    id: int
    name: str
    current_location: str
    usage_count: int
    max_usage_count: int


# --- Reports ---------------------------------------------------------------


class CostByEquipmentRead(BaseModel):
    equipment_id: int
    equipment_name: str
    total_cost: Decimal
    maintenance_count: int


class CostByMonthRead(BaseModel):
    month: str
    total_cost: Decimal


class MaintenanceCostReportRead(BaseModel):
    total_cost: Decimal
    by_equipment: list[CostByEquipmentRead]
    by_month: list[CostByMonthRead]


class SpendByPartRead(BaseModel):
    part_id: int
    part_name: str
    total_cost: Decimal
    total_quantity: int


class SpendByMonthRead(BaseModel):
    month: str
    total_cost: Decimal


class PartsSpendReportRead(BaseModel):
    total_cost: Decimal
    by_part: list[SpendByPartRead]
    by_month: list[SpendByMonthRead]


# --- Activity ---------------------------------------------------------------


class ActivityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: ActivityEventType
    description: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    equipment_id: Optional[int] = None
    equipment_name: Optional[str] = None
    part_id: Optional[int] = None
    part_name: Optional[str] = None
    occurred_at: datetime

    @classmethod
    def from_orm_event(cls, event) -> "ActivityEventRead":
        return cls(
            id=event.id,
            event_type=event.event_type,
            description=event.description,
            project_id=event.project_id,
            project_name=event.project.name if event.project else None,
            employee_id=event.employee_id,
            employee_name=event.employee.name if event.employee else None,
            equipment_id=event.equipment_id,
            equipment_name=event.equipment.name if event.equipment else None,
            part_id=event.part_id,
            part_name=event.part.name if event.part else None,
            occurred_at=event.occurred_at,
        )


# --- Employees ---------------------------------------------------------------


class EmployeeCreate(BaseModel):
    name: str
    role: EmployeeRole
    active: bool = True


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[EmployeeRole] = None
    active: Optional[bool] = None


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: EmployeeRole
    active: bool
    created_at: datetime


class EmployeeProjectRef(BaseModel):
    id: int
    name: str
    status: ProjectStatus


class EmployeeEquipmentRef(BaseModel):
    id: int
    name: str
    project_name: Optional[str] = None
    expected_return_at: datetime


class EmployeeDetailRead(EmployeeRead):
    current_projects: list[EmployeeProjectRef]
    borrowed_equipment: list[EmployeeEquipmentRef]
    recent_activity: list[ActivityEventRead]


# --- Projects ---------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    manager_id: Optional[int] = None
    start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    location: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    manager_id: Optional[int] = None
    start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    location: Optional[str] = None


class ProjectSummaryRead(BaseModel):
    id: int
    name: str
    status: ProjectStatus
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    equipment_count: int
    parts_used_count: int
    worker_count: int
    due_back_soon_count: int
    maintenance_warning_count: int


class ProjectTeamMemberRead(BaseModel):
    id: int
    name: str
    role: EmployeeRole


class ProjectEquipmentRef(BaseModel):
    id: int
    name: str
    type: str
    is_overdue: bool
    current_location: str


class ProjectPartUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    part_name: Optional[str] = None
    quantity: int
    unit_cost_at_time: Decimal
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    used_at: datetime
    note: Optional[str] = None

    @classmethod
    def from_orm_usage(cls, usage) -> "ProjectPartUsageRead":
        return cls(
            id=usage.id,
            part_id=usage.part_id,
            part_name=usage.part.name if usage.part else None,
            quantity=usage.quantity,
            unit_cost_at_time=usage.unit_cost_at_time,
            employee_id=usage.employee_id,
            employee_name=usage.employee.name if usage.employee else None,
            used_at=usage.used_at,
            note=usage.note,
        )


class MaintenanceWarningRead(BaseModel):
    equipment_id: int
    equipment_name: str
    hours_overdue: Decimal


class ProjectDetailRead(ProjectSummaryRead):
    code: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    location: Optional[str] = None
    created_at: datetime
    team: list[ProjectTeamMemberRead]
    equipment_on_site: list[ProjectEquipmentRef]
    parts_used: list[ProjectPartUsageRead]
    maintenance_warnings: list[MaintenanceWarningRead]


class ProjectPartUsageCreate(BaseModel):
    parts_used: list[PartUsageIn]
    employee_id: Optional[int] = None
    note: str = ""


class ProjectEmployeeCreate(BaseModel):
    employee_id: int


# --- Dashboard ---------------------------------------------------------------


class LocationCountRead(BaseModel):
    location: str
    count: int


class DueSoonRead(BaseModel):
    loan_id: int
    equipment_id: int
    equipment_name: str
    project_name: str
    expected_return_at: datetime
    is_overdue_for_return: bool


class DashboardSummaryRead(BaseModel):
    overdue_equipment: list[OverdueEquipmentRead]
    low_stock_parts: list[LowStockPartRead]
    discard_recommended: list[WearLimitReachedRead]
    active_projects: list[ProjectSummaryRead]
    equipment_by_location: list[LocationCountRead]
    due_soon: list[DueSoonRead]
    recent_activity: list[ActivityEventRead]


# --- Errors ---------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
