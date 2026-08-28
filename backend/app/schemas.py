from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import EquipmentStatus

# --- Equipment ---------------------------------------------------------------


class EquipmentBase(BaseModel):
    name: str
    type: str
    location: str
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    usage_hours: Decimal = Decimal("0")
    maintenance_interval_hours: Decimal
    # None = no wear limit, which is most equipment. Set only for gear
    # that's rated for a fixed number of uses.
    max_usage_count: Optional[int] = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    current_location: Optional[str] = None
    status: Optional[EquipmentStatus] = None
    usage_hours: Optional[Decimal] = None
    maintenance_interval_hours: Optional[Decimal] = None
    max_usage_count: Optional[int] = None


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
    quantity_on_hand: int = 0
    reorder_threshold: int = 0
    unit_cost: Decimal
    # Does running out actually stop work? Drives urgency, set by whoever
    # knows the part -- not inferred from usage data we don't track.
    is_critical: bool = False


class PartCreate(PartBase):
    pass


class PartUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    quantity_on_hand: Optional[int] = None
    reorder_threshold: Optional[int] = None
    unit_cost: Optional[Decimal] = None
    is_critical: Optional[bool] = None


class PartRead(PartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_low_stock: bool
    urgency: str  # "none" | "watch" | "urgent"


# --- Part restocks ---------------------------------------------------------------


class PartRestockCreate(BaseModel):
    quantity: int = Field(gt=0)
    unit_cost: Decimal
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
    project: str
    manager_name: str
    borrower_name: str
    expected_return_at: datetime


class EquipmentLoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    project: str
    manager_name: str
    borrower_name: str
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
            manager_name=loan.manager_name,
            borrower_name=loan.borrower_name,
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


# --- Errors ---------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
