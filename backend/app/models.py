import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EquipmentStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DOWN = "down"
    MAINTENANCE = "maintenance"


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Home/storage location -- where this equipment lives when nothing has
    # it checked out. `current_location` (below) is where it actually is
    # right now, and moves with checkout/return.
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    current_location: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[EquipmentStatus] = mapped_column(
        SAEnum(EquipmentStatus, name="equipment_status"),
        nullable=False,
        default=EquipmentStatus.OPERATIONAL,
    )
    # Numeric, not Float: the overdue check is an exact >= comparison, and
    # usage_hours accumulates from repeated updates -- float rounding drift
    # could eventually put equipment on the wrong side of the threshold.
    usage_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    last_maintenance_usage_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    maintenance_interval_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Wear-limit tracking: some equipment is only rated for a fixed number
    # of uses (each checkout counts as one), independent of the hour-based
    # maintenance interval above. max_usage_count is null for equipment
    # with no such limit -- most of the fleet.
    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)
    max_usage_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    maintenance_logs: Mapped[list["MaintenanceLog"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    loans: Mapped[list["EquipmentLoan"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    quantity_on_hand: Mapped[int] = mapped_column(nullable=False, default=0)
    reorder_threshold: Mapped[int] = mapped_column(nullable=False, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Manually set by whoever knows the part: does running out actually stop
    # work (safety gear, a part with no substitute), or can it wait a few
    # days for a restock? Drives urgency, not just the low-stock flag.
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    usages: Mapped[list["PartUsed"]] = relationship(back_populates="part")
    restocks: Mapped[list["PartRestock"]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    equipment: Mapped["Equipment"] = relationship(back_populates="maintenance_logs")
    parts_used: Mapped[list["PartUsed"]] = relationship(
        back_populates="maintenance_log", cascade="all, delete-orphan"
    )


class PartUsed(Base):
    __tablename__ = "parts_used"

    maintenance_log_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_logs.id"), primary_key=True
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    # Snapshot of Part.unit_cost at the moment this maintenance was logged.
    # Cost reports read this, not the part's current price -- otherwise a
    # price change today would silently rewrite the cost of a job from six
    # months ago.
    unit_cost_at_time: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    maintenance_log: Mapped["MaintenanceLog"] = relationship(back_populates="parts_used")
    part: Mapped["Part"] = relationship(back_populates="usages")


class EquipmentLoan(Base):
    """One borrow/return cycle. `returned_at is None` means the loan is
    still active -- that's how we know a piece of equipment is currently
    checked out, without a separate boolean to keep in sync."""

    __tablename__ = "equipment_loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    project: Mapped[str] = mapped_column(String(200), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(200), nullable=False)
    borrower_name: Mapped[str] = mapped_column(String(200), nullable=False)
    checked_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_return_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="loans")


class PartRestock(Base):
    """One inbound shipment. Stock only ever went down (consumed by
    maintenance) before this existed -- this is the other half of the
    inventory story: how it came back, when, from whom, and at what price.
    unit_cost here is what was actually paid for this shipment; Part.unit_cost
    is updated to match, so future maintenance cost snapshots reflect the
    latest price without rewriting history."""

    __tablename__ = "part_restocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    restocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    part: Mapped["Part"] = relationship(back_populates="restocks")
