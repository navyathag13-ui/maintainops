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


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    status: Optional[EquipmentStatus] = None
    usage_hours: Optional[Decimal] = None
    maintenance_interval_hours: Optional[Decimal] = None


class EquipmentRead(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_maintenance_usage_hours: Decimal
    is_overdue: bool


# --- Parts ---------------------------------------------------------------


class PartBase(BaseModel):
    name: str
    sku: str
    quantity_on_hand: int = 0
    reorder_threshold: int = 0
    unit_cost: Decimal


class PartCreate(PartBase):
    pass


class PartUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    quantity_on_hand: Optional[int] = None
    reorder_threshold: Optional[int] = None
    unit_cost: Optional[Decimal] = None


class PartRead(PartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_low_stock: bool


# --- Maintenance logs ---------------------------------------------------------------


class PartUsageIn(BaseModel):
    part_id: int
    quantity: int = Field(gt=0)


class PartUsedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    part_id: int
    quantity: int
    part_name: Optional[str] = None

    @classmethod
    def from_orm_with_part_name(cls, part_used) -> "PartUsedRead":
        return cls(
            part_id=part_used.part_id,
            quantity=part_used.quantity,
            part_name=part_used.part.name if part_used.part else None,
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


# --- Errors ---------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
