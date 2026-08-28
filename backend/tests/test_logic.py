from datetime import datetime, timezone

import pytest

from app.logic import (
    DuplicatePartInRequestError,
    EmployeeNotFoundError,
    EquipmentAlreadyCheckedOutError,
    EquipmentNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
    LoanAlreadyReturnedError,
    LoanNotFoundError,
    PartNotFoundError,
    PartUsageInput,
    ProjectNotFoundError,
    check_out_equipment,
    is_equipment_at_wear_limit,
    is_equipment_overdue,
    is_part_low_stock,
    part_urgency,
    record_maintenance,
    restock_part,
    return_equipment,
    use_parts_on_project,
)
from app.models import (
    ActivityEvent,
    ActivityEventType,
    Employee,
    EmployeeRole,
    Equipment,
    EquipmentLoan,
    MaintenanceLog,
    Part,
    Project,
    ProjectPartUsage,
    ProjectStatus,
)
from app.reports import maintenance_cost_report, parts_spend_report


def make_equipment(**overrides) -> Equipment:
    defaults = dict(
        name="Pump 1",
        type="pump",
        location="Building A",
        usage_hours=0.0,
        last_maintenance_usage_hours=0.0,
        maintenance_interval_hours=500.0,
        usage_count=0,
        max_usage_count=None,
    )
    defaults.update(overrides)
    # current_location defaults to the home location unless explicitly overridden.
    defaults.setdefault("current_location", defaults["location"])
    return Equipment(**defaults)


def make_part(**overrides) -> Part:
    defaults = dict(
        name="Filter",
        sku="FLT-001",
        quantity_on_hand=10,
        reorder_threshold=3,
        unit_cost=12.50,
        is_critical=False,
    )
    defaults.update(overrides)
    return Part(**defaults)


def make_project(**overrides) -> Project:
    defaults = dict(
        name="House #1",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Project(**defaults)


def make_employee(**overrides) -> Employee:
    defaults = dict(
        name="Alex Carter",
        role=EmployeeRole.TECHNICIAN,
        active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Employee(**defaults)


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


# --- is_equipment_at_wear_limit ---------------------------------------------


class TestIsEquipmentAtWearLimit:
    def test_no_limit_set_is_never_at_limit(self):
        equipment = make_equipment(usage_count=999, max_usage_count=None)
        assert is_equipment_at_wear_limit(equipment) is False

    def test_under_limit(self):
        equipment = make_equipment(usage_count=3, max_usage_count=5)
        assert is_equipment_at_wear_limit(equipment) is False

    def test_exactly_at_limit_counts_as_reached(self):
        equipment = make_equipment(usage_count=5, max_usage_count=5)
        assert is_equipment_at_wear_limit(equipment) is True

    def test_over_limit(self):
        equipment = make_equipment(usage_count=6, max_usage_count=5)
        assert is_equipment_at_wear_limit(equipment) is True

    def test_zero_limit_means_any_use_trips_it(self):
        equipment = make_equipment(usage_count=0, max_usage_count=0)
        assert is_equipment_at_wear_limit(equipment) is True


# --- part_urgency ------------------------------------------------------------


class TestPartUrgency:
    def test_not_low_stock_is_none_regardless_of_criticality(self):
        part = make_part(quantity_on_hand=10, reorder_threshold=3, is_critical=True)
        assert part_urgency(part) == "none"

    def test_low_stock_not_critical_is_watch(self):
        part = make_part(quantity_on_hand=2, reorder_threshold=3, is_critical=False)
        assert part_urgency(part) == "watch"

    def test_low_stock_critical_is_urgent(self):
        part = make_part(quantity_on_hand=2, reorder_threshold=3, is_critical=True)
        assert part_urgency(part) == "urgent"

    def test_exactly_at_threshold_critical_is_urgent(self):
        part = make_part(quantity_on_hand=3, reorder_threshold=3, is_critical=True)
        assert part_urgency(part) == "urgent"

    def test_zero_stock_critical_is_urgent(self):
        part = make_part(quantity_on_hand=0, reorder_threshold=3, is_critical=True)
        assert part_urgency(part) == "urgent"


# --- check_out_equipment / return_equipment -----------------------------------


class TestCheckOutAndReturnEquipment:
    def test_checkout_creates_loan_moves_location_and_counts_a_use(self, db_session):
        equipment = make_equipment(location="Garage Back Storage 3", max_usage_count=5)
        manager = make_employee(name="Jake Morgan", role=EmployeeRole.MANAGER)
        borrower = make_employee(name="Alex Carter")
        project = make_project(name="House #1")
        db_session.add_all([equipment, manager, borrower, project])
        db_session.flush()
        project.manager_id = manager.id
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=borrower.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        assert isinstance(loan, EquipmentLoan)
        assert loan.returned_at is None
        assert loan.project_id == project.id
        assert loan.borrower_employee_id == borrower.id
        # String fields derived from the linked records, not typed by hand --
        # every existing reader of these columns keeps working unchanged.
        assert loan.project == "House #1"
        assert loan.manager_name == "Jake Morgan"
        assert loan.borrower_name == "Alex Carter"
        assert equipment.current_location == "House #1"
        assert equipment.usage_count == 1
        assert is_equipment_at_wear_limit(equipment) is False

    def test_checkout_derives_manager_from_project_not_a_parameter(self, db_session):
        # There's no manager_name parameter at all anymore -- it can only
        # come from the project's own manager_id.
        equipment = make_equipment()
        manager = make_employee(name="Maya Patel", role=EmployeeRole.MANAGER)
        borrower = make_employee(name="Ethan Davis", role=EmployeeRole.EQUIPMENT_OPERATOR)
        project = make_project(name="Mall Construction #4")
        db_session.add_all([equipment, manager, borrower, project])
        db_session.flush()
        project.manager_id = manager.id
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=borrower.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        assert loan.manager_name == "Maya Patel"

    def test_checkout_with_no_project_manager_falls_back_cleanly(self, db_session):
        equipment = make_equipment()
        borrower = make_employee()
        project = make_project()  # no manager_id set
        db_session.add_all([equipment, borrower, project])
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=borrower.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        assert loan.manager_name == "Unassigned"

    def test_checkout_while_already_checked_out_is_rejected(self, db_session):
        equipment = make_equipment()
        employee = make_employee()
        project_a = make_project(name="House #1")
        project_b = make_project(name="Mall Construction #4")
        db_session.add_all([equipment, employee, project_a, project_b])
        db_session.flush()

        check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project_a.id,
            borrower_employee_id=employee.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        with pytest.raises(EquipmentAlreadyCheckedOutError):
            check_out_equipment(
                db_session,
                equipment_id=equipment.id,
                project_id=project_b.id,
                borrower_employee_id=employee.id,
                expected_return_at=datetime.now(timezone.utc),
            )

        # Still out at the first project -- the second attempt didn't move it.
        assert equipment.current_location == "House #1"
        assert equipment.usage_count == 1

    def test_checkout_unknown_equipment_raises(self, db_session):
        employee = make_employee()
        project = make_project()
        db_session.add_all([employee, project])
        db_session.flush()

        with pytest.raises(EquipmentNotFoundError):
            check_out_equipment(
                db_session,
                equipment_id=999,
                project_id=project.id,
                borrower_employee_id=employee.id,
                expected_return_at=datetime.now(timezone.utc),
            )

    def test_checkout_unknown_project_raises(self, db_session):
        equipment = make_equipment()
        employee = make_employee()
        db_session.add_all([equipment, employee])
        db_session.flush()

        with pytest.raises(ProjectNotFoundError):
            check_out_equipment(
                db_session,
                equipment_id=equipment.id,
                project_id=999,
                borrower_employee_id=employee.id,
                expected_return_at=datetime.now(timezone.utc),
            )

    def test_checkout_unknown_employee_raises(self, db_session):
        equipment = make_equipment()
        project = make_project()
        db_session.add_all([equipment, project])
        db_session.flush()

        with pytest.raises(EmployeeNotFoundError):
            check_out_equipment(
                db_session,
                equipment_id=equipment.id,
                project_id=project.id,
                borrower_employee_id=999,
                expected_return_at=datetime.now(timezone.utc),
            )

    def test_return_moves_equipment_back_to_home_location(self, db_session):
        equipment = make_equipment(location="Garage Back Storage 3")
        employee = make_employee()
        project = make_project()
        db_session.add_all([equipment, employee, project])
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=employee.id,
            expected_return_at=datetime.now(timezone.utc),
        )
        assert equipment.current_location == project.name

        returned = return_equipment(db_session, loan.id)

        assert returned.returned_at is not None
        assert equipment.current_location == "Garage Back Storage 3"

    def test_return_allows_a_fresh_checkout_afterward(self, db_session):
        equipment = make_equipment(max_usage_count=5)
        employee_a = make_employee(name="Alex Carter")
        employee_b = make_employee(name="Priya Shah")
        project_a = make_project(name="House #1")
        project_b = make_project(name="Mall Construction #4")
        db_session.add_all([equipment, employee_a, employee_b, project_a, project_b])
        db_session.flush()

        first_loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project_a.id,
            borrower_employee_id=employee_a.id,
            expected_return_at=datetime.now(timezone.utc),
        )
        return_equipment(db_session, first_loan.id)

        second_loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project_b.id,
            borrower_employee_id=employee_b.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        assert second_loan.id != first_loan.id
        assert equipment.current_location == "Mall Construction #4"
        assert equipment.usage_count == 2

    def test_return_already_returned_loan_is_rejected(self, db_session):
        equipment = make_equipment()
        employee = make_employee()
        project = make_project()
        db_session.add_all([equipment, employee, project])
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=employee.id,
            expected_return_at=datetime.now(timezone.utc),
        )
        return_equipment(db_session, loan.id)

        with pytest.raises(LoanAlreadyReturnedError):
            return_equipment(db_session, loan.id)

    def test_return_unknown_loan_raises(self, db_session):
        with pytest.raises(LoanNotFoundError):
            return_equipment(db_session, 999)

    def test_checkout_that_hits_wear_limit_is_still_allowed_but_flagged(self, db_session):
        # The 5th use is allowed -- it's the checkout itself that trips the
        # flag, not a block. Discard is a human decision, not an
        # auto-enforced lockout.
        equipment = make_equipment(usage_count=4, max_usage_count=5)
        employee = make_employee()
        project = make_project()
        db_session.add_all([equipment, employee, project])
        db_session.flush()

        check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=employee.id,
            expected_return_at=datetime.now(timezone.utc),
        )

        assert equipment.usage_count == 5
        assert is_equipment_at_wear_limit(equipment) is True

    def test_checkout_and_return_each_log_one_activity_event(self, db_session):
        equipment = make_equipment(name="Generator #02")
        employee = make_employee(name="Ethan Davis")
        project = make_project(name="Mall Construction #4")
        db_session.add_all([equipment, employee, project])
        db_session.flush()

        loan = check_out_equipment(
            db_session,
            equipment_id=equipment.id,
            project_id=project.id,
            borrower_employee_id=employee.id,
            expected_return_at=datetime.now(timezone.utc),
        )
        return_equipment(db_session, loan.id)

        events = db_session.query(ActivityEvent).order_by(ActivityEvent.id).all()
        assert [e.event_type for e in events] == [
            ActivityEventType.EQUIPMENT_CHECKED_OUT,
            ActivityEventType.EQUIPMENT_RETURNED,
        ]
        assert "Ethan Davis checked out Generator #02 for Mall Construction #4" in events[0].description
        assert "Ethan Davis returned Generator #02" in events[1].description


# --- record_maintenance cost snapshot ----------------------------------------


class TestMaintenanceCostSnapshot:
    def test_part_used_snapshots_price_at_time_of_service(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, unit_cost=12.50)
        db_session.add_all([equipment, part])
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Replaced filter",
            parts_used=[PartUsageInput(part_id=part.id, quantity=2)],
        )

        assert log.parts_used[0].unit_cost_at_time == 12.50

    def test_later_price_change_does_not_rewrite_history(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, unit_cost=12.50)
        db_session.add_all([equipment, part])
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Replaced filter",
            parts_used=[PartUsageInput(part_id=part.id, quantity=2)],
        )
        original_snapshot = log.parts_used[0].unit_cost_at_time

        # Price goes up after the fact (e.g. a new shipment came in pricier).
        part.unit_cost = 20.00
        db_session.flush()

        assert log.parts_used[0].unit_cost_at_time == original_snapshot == 12.50


# --- restock_part --------------------------------------------------------------


class TestRestockPart:
    def test_happy_path_increments_stock_and_updates_price(self, db_session):
        part = make_part(quantity_on_hand=1, unit_cost=12.50)
        db_session.add(part)
        db_session.flush()

        restock = restock_part(
            db_session,
            part_id=part.id,
            quantity=20,
            unit_cost=13.75,
            supplier="Acme Supply Co",
        )

        assert restock.quantity == 20
        assert restock.unit_cost == 13.75
        assert part.quantity_on_hand == 21
        assert part.unit_cost == 13.75

    def test_zero_quantity_rejected(self, db_session):
        part = make_part(quantity_on_hand=1)
        db_session.add(part)
        db_session.flush()

        with pytest.raises(InvalidQuantityError):
            restock_part(db_session, part_id=part.id, quantity=0, unit_cost=12.50, supplier="Acme")
        assert part.quantity_on_hand == 1

    def test_negative_quantity_rejected(self, db_session):
        part = make_part(quantity_on_hand=1)
        db_session.add(part)
        db_session.flush()

        with pytest.raises(InvalidQuantityError):
            restock_part(db_session, part_id=part.id, quantity=-5, unit_cost=12.50, supplier="Acme")
        assert part.quantity_on_hand == 1

    def test_unknown_part_raises(self, db_session):
        with pytest.raises(PartNotFoundError):
            restock_part(db_session, part_id=999, quantity=10, unit_cost=12.50, supplier="Acme")

    def test_restock_does_not_touch_past_maintenance_cost_snapshots(self, db_session):
        equipment = make_equipment()
        part = make_part(quantity_on_hand=10, unit_cost=12.50)
        db_session.add_all([equipment, part])
        db_session.flush()

        log = record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Replaced filter",
            parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
        )

        restock_part(db_session, part_id=part.id, quantity=50, unit_cost=99.00, supplier="Acme")

        assert log.parts_used[0].unit_cost_at_time == 12.50
        assert part.unit_cost == 99.00


# --- reports.maintenance_cost_report ------------------------------------------


class TestMaintenanceCostReport:
    def test_no_logs_gives_zero_report(self, db_session):
        report = maintenance_cost_report(db_session)
        assert report.total_cost == 0
        assert report.by_equipment == []
        assert report.by_month == []

    def test_aggregates_across_equipment_and_month(self, db_session):
        equipment_a = make_equipment(name="Pump 1")
        equipment_b = make_equipment(name="Pump 2")
        part = make_part(quantity_on_hand=100, unit_cost=10.00)
        db_session.add_all([equipment_a, equipment_b, part])
        db_session.flush()

        record_maintenance(
            db_session,
            equipment_id=equipment_a.id,
            performed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
            description="Service 1",
            parts_used=[PartUsageInput(part_id=part.id, quantity=2)],  # $20
        )
        record_maintenance(
            db_session,
            equipment_id=equipment_a.id,
            performed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            description="Service 2",
            parts_used=[PartUsageInput(part_id=part.id, quantity=1)],  # $10
        )
        record_maintenance(
            db_session,
            equipment_id=equipment_b.id,
            performed_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
            description="Service 3",
            parts_used=[PartUsageInput(part_id=part.id, quantity=5)],  # $50
        )

        report = maintenance_cost_report(db_session)

        assert report.total_cost == 80
        # Sorted by total_cost descending -> equipment_b ($50) before equipment_a ($30)
        assert report.by_equipment[0].equipment_name == "Pump 2"
        assert report.by_equipment[0].total_cost == 50
        assert report.by_equipment[0].maintenance_count == 1
        assert report.by_equipment[1].equipment_name == "Pump 1"
        assert report.by_equipment[1].total_cost == 30
        assert report.by_equipment[1].maintenance_count == 2

        by_month = {m.month: m.total_cost for m in report.by_month}
        assert by_month == {"2026-06": 70, "2026-07": 10}

    def test_maintenance_log_with_no_parts_contributes_zero_cost(self, db_session):
        equipment = make_equipment()
        db_session.add(equipment)
        db_session.flush()

        record_maintenance(
            db_session,
            equipment_id=equipment.id,
            performed_at=datetime.now(timezone.utc),
            description="Visual inspection only",
            parts_used=[],
        )

        report = maintenance_cost_report(db_session)
        assert report.total_cost == 0
        assert report.by_equipment[0].maintenance_count == 1
        assert report.by_equipment[0].total_cost == 0


# --- reports.parts_spend_report ------------------------------------------------


class TestPartsSpendReport:
    def test_no_restocks_gives_zero_report(self, db_session):
        report = parts_spend_report(db_session)
        assert report.total_cost == 0
        assert report.by_part == []
        assert report.by_month == []

    def test_aggregates_across_parts_and_month(self, db_session):
        part_a = make_part(name="Filter", sku="FLT-001", quantity_on_hand=0)
        part_b = make_part(name="Belt", sku="BLT-001", quantity_on_hand=0)
        db_session.add_all([part_a, part_b])
        db_session.flush()

        restock_part(db_session, part_id=part_a.id, quantity=10, unit_cost=5.00, supplier="Acme")
        restock_part(db_session, part_id=part_b.id, quantity=4, unit_cost=25.00, supplier="Acme")

        report = parts_spend_report(db_session)

        assert report.total_cost == 150  # 10*5 + 4*25
        assert report.by_part[0].part_name == "Belt"
        assert report.by_part[0].total_cost == 100
        assert report.by_part[1].part_name == "Filter"
        assert report.by_part[1].total_cost == 50


# --- use_parts_on_project ------------------------------------------------------


class TestUsePartsOnProject:
    def test_happy_path_decrements_stock_and_records_usage(self, db_session):
        project = make_project(name="House #1")
        employee = make_employee(name="Alex Carter")
        part = make_part(name="Wood Screws", quantity_on_hand=100, reorder_threshold=85, unit_cost=0.10)
        db_session.add_all([project, employee, part])
        db_session.flush()

        usages = use_parts_on_project(
            db_session,
            project_id=project.id,
            employee_id=employee.id,
            parts_used=[PartUsageInput(part_id=part.id, quantity=20)],
        )

        assert len(usages) == 1
        assert usages[0].quantity == 20
        assert usages[0].unit_cost_at_time == part.unit_cost
        assert part.quantity_on_hand == 80

    def test_employee_is_optional(self, db_session):
        project = make_project()
        part = make_part(quantity_on_hand=10)
        db_session.add_all([project, part])
        db_session.flush()

        usages = use_parts_on_project(
            db_session,
            project_id=project.id,
            employee_id=None,
            parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
        )

        assert usages[0].employee_id is None

    def test_insufficient_stock_on_one_part_rejects_whole_request(self, db_session):
        project = make_project()
        part_ok = make_part(name="Wood Screws", sku="WS-1", quantity_on_hand=100)
        part_short = make_part(name="Anchor Bolts", sku="AB-1", quantity_on_hand=2)
        db_session.add_all([project, part_ok, part_short])
        db_session.flush()

        with pytest.raises(InsufficientStockError) as exc_info:
            use_parts_on_project(
                db_session,
                project_id=project.id,
                employee_id=None,
                parts_used=[
                    PartUsageInput(part_id=part_ok.id, quantity=5),
                    PartUsageInput(part_id=part_short.id, quantity=10),
                ],
            )

        assert {s.part_id for s in exc_info.value.shortfalls} == {part_short.id}
        # All-or-nothing: the plentiful part must be untouched too.
        assert part_ok.quantity_on_hand == 100
        assert part_short.quantity_on_hand == 2

    def test_zero_quantity_rejected(self, db_session):
        project = make_project()
        part = make_part(quantity_on_hand=10)
        db_session.add_all([project, part])
        db_session.flush()

        with pytest.raises(InvalidQuantityError):
            use_parts_on_project(
                db_session,
                project_id=project.id,
                employee_id=None,
                parts_used=[PartUsageInput(part_id=part.id, quantity=0)],
            )
        assert part.quantity_on_hand == 10

    def test_duplicate_part_rejected(self, db_session):
        project = make_project()
        part = make_part(quantity_on_hand=10)
        db_session.add_all([project, part])
        db_session.flush()

        with pytest.raises(DuplicatePartInRequestError):
            use_parts_on_project(
                db_session,
                project_id=project.id,
                employee_id=None,
                parts_used=[
                    PartUsageInput(part_id=part.id, quantity=1),
                    PartUsageInput(part_id=part.id, quantity=2),
                ],
            )

    def test_unknown_project_raises(self, db_session):
        part = make_part(quantity_on_hand=10)
        db_session.add(part)
        db_session.flush()

        with pytest.raises(ProjectNotFoundError):
            use_parts_on_project(
                db_session,
                project_id=999,
                employee_id=None,
                parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
            )

    def test_unknown_employee_raises(self, db_session):
        project = make_project()
        part = make_part(quantity_on_hand=10)
        db_session.add_all([project, part])
        db_session.flush()

        with pytest.raises(EmployeeNotFoundError):
            use_parts_on_project(
                db_session,
                project_id=project.id,
                employee_id=999,
                parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
            )

    def test_unknown_part_raises(self, db_session):
        project = make_project()
        db_session.add(project)
        db_session.flush()

        with pytest.raises(PartNotFoundError):
            use_parts_on_project(
                db_session,
                project_id=project.id,
                employee_id=None,
                parts_used=[PartUsageInput(part_id=999, quantity=1)],
            )

    def test_crossing_reorder_threshold_logs_low_stock_activity_once(self, db_session):
        project = make_project()
        part = make_part(name="Grinding Disc", quantity_on_hand=6, reorder_threshold=5)
        db_session.add_all([project, part])
        db_session.flush()

        # First use: 6 -> 5, which is already <= threshold (5) -- crosses now.
        use_parts_on_project(
            db_session, project_id=project.id, employee_id=None,
            parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
        )
        # Second use: 5 -> 4, still low, but already was -- no duplicate event.
        use_parts_on_project(
            db_session, project_id=project.id, employee_id=None,
            parts_used=[PartUsageInput(part_id=part.id, quantity=1)],
        )

        low_stock_events = (
            db_session.query(ActivityEvent)
            .filter(ActivityEvent.event_type == ActivityEventType.LOW_STOCK_REACHED)
            .all()
        )
        assert len(low_stock_events) == 1
        assert part.quantity_on_hand == 4

    def test_logs_one_activity_event_per_part_used(self, db_session):
        project = make_project(name="House #1")
        employee = make_employee(name="Priya Shah")
        part = make_part(name="Drill Bits", quantity_on_hand=50)
        db_session.add_all([project, employee, part])
        db_session.flush()

        use_parts_on_project(
            db_session,
            project_id=project.id,
            employee_id=employee.id,
            parts_used=[PartUsageInput(part_id=part.id, quantity=3)],
        )

        events = (
            db_session.query(ActivityEvent)
            .filter(ActivityEvent.event_type == ActivityEventType.PART_USED_ON_PROJECT)
            .all()
        )
        assert len(events) == 1
        assert "Priya Shah used 3 Drill Bits on House #1" in events[0].description
