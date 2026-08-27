from datetime import datetime, timezone

import pytest

from app.logic import (
    DuplicatePartInRequestError,
    EquipmentNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
    PartNotFoundError,
    PartUsageInput,
    is_equipment_overdue,
    is_part_low_stock,
    record_maintenance,
)
from app.models import Equipment, MaintenanceLog, Part


def make_equipment(**overrides) -> Equipment:
    defaults = dict(
        name="Pump 1",
        type="pump",
        location="Building A",
        usage_hours=0.0,
        last_maintenance_usage_hours=0.0,
        maintenance_interval_hours=500.0,
    )
    defaults.update(overrides)
    return Equipment(**defaults)


def make_part(**overrides) -> Part:
    defaults = dict(
        name="Filter",
        sku="FLT-001",
        quantity_on_hand=10,
        reorder_threshold=3,
        unit_cost=12.50,
    )
    defaults.update(overrides)
    return Part(**defaults)


# --- is_equipment_overdue --------------------------------------------------


class TestIsEquipmentOverdue:
    def test_not_overdue_well_under_interval(self):
        equipment = make_equipment(usage_hours=100, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is False

    def test_overdue_past_interval(self):
        equipment = make_equipment(usage_hours=600, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is True

    def test_exactly_at_threshold_counts_as_overdue(self):
        equipment = make_equipment(usage_hours=500, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is True

    def test_one_hour_under_threshold_is_not_overdue(self):
        equipment = make_equipment(usage_hours=499, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is False

    def test_no_maintenance_history_yet_uses_zero_baseline(self):
        # Brand-new equipment: last_maintenance_usage_hours defaults to 0,
        # so it becomes overdue purely once usage crosses the interval.
        equipment = make_equipment(usage_hours=500, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is True

        equipment_not_yet = make_equipment(usage_hours=499, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment_not_yet) is False

    def test_overdue_check_is_relative_to_last_service_not_absolute_usage(self):
        # 1200 total usage hours, serviced at 1000 -> only 200 hours since
        # service, well under a 500-hour interval. Confirms the check is
        # usage-since-last-service, not raw usage_hours.
        equipment = make_equipment(usage_hours=1200, last_maintenance_usage_hours=1000, maintenance_interval_hours=500)
        assert is_equipment_overdue(equipment) is False


# --- is_part_low_stock ------------------------------------------------------


class TestIsPartLowStock:
    def test_well_above_threshold_is_not_low(self):
        part = make_part(quantity_on_hand=10, reorder_threshold=3)
        assert is_part_low_stock(part) is False

    def test_exactly_at_threshold_counts_as_low(self):
        part = make_part(quantity_on_hand=3, reorder_threshold=3)
        assert is_part_low_stock(part) is True

    def test_below_threshold_is_low(self):
        part = make_part(quantity_on_hand=1, reorder_threshold=3)
        assert is_part_low_stock(part) is True

    def test_zero_stock_is_low(self):
        part = make_part(quantity_on_hand=0, reorder_threshold=3)
        assert is_part_low_stock(part) is True

    def test_zero_threshold_zero_stock_is_low(self):
        part = make_part(quantity_on_hand=0, reorder_threshold=0)
        assert is_part_low_stock(part) is True


# --- record_maintenance ------------------------------------------------------


class TestRecordMaintenance:
    def test_happy_path_single_part_decrements_stock_and_creates_log(self, db_session):
        equipment = make_equipment(usage_hours=600, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        part = make_part(quantity_on_hand=10, reorder_threshold=3)
        db_session.add_all([equipment, part])
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Replaced filter",
            parts_used=[PartUsageInput(part_id=part.id, quantity=2)],
        )

        assert isinstance(log, MaintenanceLog)
        assert log.equipment_id == equipment.id
        assert len(log.parts_used) == 1
        assert log.parts_used[0].quantity == 2
        assert part.quantity_on_hand == 8
        # Baseline reset to current usage -> no longer overdue.
        assert equipment.last_maintenance_usage_hours == 600
        assert is_equipment_overdue(equipment) is False

    def test_happy_path_multiple_parts(self, db_session):
        equipment = make_equipment()
        part_a = make_part(name="Filter", sku="FLT-001", quantity_on_hand=10, reorder_threshold=3)
        part_b = make_part(name="Belt", sku="BLT-001", quantity_on_hand=5, reorder_threshold=1)
        db_session.add_all([equipment, part_a, part_b])
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Routine service",
            parts_used=[
                PartUsageInput(part_id=part_a.id, quantity=2),
                PartUsageInput(part_id=part_b.id, quantity=1),
            ],
        )

        assert len(log.parts_used) == 2
        assert part_a.quantity_on_hand == 8
        assert part_b.quantity_on_hand == 4

    def test_consuming_exact_remaining_quantity_succeeds(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=2, reorder_threshold=1)
        db_session.add_all([equipment, part])
        db_session.flush()

        record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Used it all",
            parts_used=[PartUsageInput(part_id=part.id, quantity=2)],
        )

        assert part.quantity_on_hand == 0

    def test_zero_stock_part_rejected(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=0, reorder_threshold=3)
        db_session.add_all([equipment, part])
        db_session.flush()

        with pytest.raises(InsufficientStockError) as exc_info:
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Needs a part we don't have",
                parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
            )

        assert exc_info.value.shortfalls[0].part_id == part.id
        assert exc_info.value.shortfalls[0].available == 0
        # Nothing should have moved.
        assert part.quantity_on_hand == 0

    def test_insufficient_stock_on_one_part_rejects_whole_log_atomically(self, db_session):
        equipment = make_equipment()
        part_ok = make_part(name="Filter", sku="FLT-001", quantity_on_hand=10, reorder_threshold=3)
        part_short = make_part(name="Belt", sku="BLT-001", quantity_on_hand=1, reorder_threshold=1)
        db_session.add_all([equipment, part_ok, part_short])
        db_session.flush()

        with pytest.raises(InsufficientStockError) as exc_info:
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Multi-part job, one part short",
                parts_used=[
                    PartUsageInput(part_id=part_ok.id, quantity=2),
                    PartUsageInput(part_id=part_short.id, quantity=5),
                ],
            )

        shortfall_part_ids = {s.part_id for s in exc_info.value.shortfalls}
        assert shortfall_part_ids == {part_short.id}
        # The plentiful part must NOT have been decremented -- all-or-nothing.
        assert part_ok.quantity_on_hand == 10
        assert part_short.quantity_on_hand == 1
        # And the equipment baseline must be untouched.
        assert equipment.last_maintenance_usage_hours == 0

    def test_unknown_equipment_raises(self, db_session):
        with pytest.raises(EquipmentNotFoundError):
            record_maintenance(
                db_session,
                equipment_id=999,
                performed_at=datetime.now(timezone.utc),
                description="No such equipment",
                parts_used=[],
            )

    def test_unknown_part_raises(self, db_session):
        equipment = make_equipment()
        db_session.add(equipment)
        db_session.flush()

        with pytest.raises(PartNotFoundError):
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Bogus part id",
                parts_used=[PartUsageInput(part_id=999, quantity=1)],
            )

    def test_maintenance_log_with_no_parts_used_still_resets_baseline(self, db_session):
        # A log entry doesn't have to consume parts (e.g. an inspection).
        equipment = make_equipment(usage_hours=700, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        db_session.add(equipment)
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Visual inspection only",
            parts_used=[],
        )

        assert log.parts_used == []
        assert equipment.last_maintenance_usage_hours == 700

    def test_zero_quantity_rejected(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, reorder_threshold=3)
        db_session.add_all([equipment, part])
        db_session.flush()

        with pytest.raises(InvalidQuantityError):
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Zero quantity is not a real usage",
                parts_used=[PartUsageInput(part_id=part.id, quantity=0)],
            )
        assert part.quantity_on_hand == 10

    def test_negative_quantity_rejected(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, reorder_threshold=3)
        db_session.add_all([equipment, part])
        db_session.flush()

        with pytest.raises(InvalidQuantityError):
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Negative quantity would increase stock",
                parts_used=[PartUsageInput(part_id=part.id, quantity=-1)],
            )
        assert part.quantity_on_hand == 10

    def test_duplicate_part_in_same_request_rejected(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, reorder_threshold=3)
        db_session.add_all([equipment, part])
        db_session.flush()

        with pytest.raises(DuplicatePartInRequestError):
            record_maintenance(
                db_session,
                equipment_id=equipment.id,
                performed_at=datetime.now(timezone.utc),
                description="Same part listed twice",
                parts_used=[
                    PartUsageInput(part_id=part.id, quantity=1),
                    PartUsageInput(part_id=part.id, quantity=2),
                ],
            )
        # Rejected before any DB mutation.
        assert part.quantity_on_hand == 10

    def test_equipment_with_no_prior_maintenance_history_can_be_serviced(self, db_session):
        # First-ever service on equipment that has never been maintained.
        equipment = make_equipment(usage_hours=250, last_maintenance_usage_hours=0, maintenance_interval_hours=500)
        db_session.add(equipment)
        db_session.flush()

        assert equipment.maintenance_logs == []

        record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="First scheduled service",
            parts_used=[],
        )

        assert len(equipment.maintenance_logs) == 1
        assert equipment.last_maintenance_usage_hours == 250
