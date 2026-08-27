import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
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
    location: Mapped[str] = mapped_column(String(200), nullable=False)
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

    maintenance_logs: Mapped[list["MaintenanceLog"]] = relationship(
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

    usages: Mapped[list["PartUsed"]] = relationship(back_populates="part")


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

    maintenance_log: Mapped["MaintenanceLog"] = relationship(back_populates="parts_used")
    part: Mapped["Part"] = relationship(back_populates="usages")
