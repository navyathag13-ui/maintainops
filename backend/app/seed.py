"""Demo data. Runs automatically on startup if the equipment table is
empty (see main.py's lifespan) -- the spec behind this feature set was
explicit that a fresh clone should look like a system a small company has
already been using, not empty tables. Idempotent in the sense that it only
ever runs once per database: it checks emptiness, not "has this exact data",
so it won't duplicate on every restart, but it also won't merge with
hand-entered data from a previous run in any smart way.

Most equipment gets its usage/wear state baked in directly (there's no
narrative reason 30 healthy drills need a simulated checkout history). The
specific scenarios the demo is built around -- Cordless Drill #03 out on
House #1, Concrete Mixer #01 overdue, Safety Harness #02 hitting its wear
limit, Wood Screws crossing its reorder threshold -- go through the real
logic.py functions, so they generate real ActivityEvent rows and the demo's
Activity feed has an actual story in it, not just static rows.
"""

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .logic import (
    PartUsageInput,
    check_out_equipment,
    log_activity,
    record_maintenance,
    restock_part,
    return_equipment,
    use_parts_on_project,
)
from .models import (
    ActivityEventType,
    Employee,
    EmployeeRole,
    Equipment,
    EquipmentStatus,
    Part,
    Project,
    ProjectEmployee,
    ProjectStatus,
)

HOME_LOCATION = "Garage / Storage"


def is_seeded(db: Session) -> bool:
    return db.execute(select(func.count()).select_from(Equipment)).scalar_one() > 0


def seed_demo_data(db: Session) -> None:
    now = datetime.now(timezone.utc)
    rng = random.Random(42)  # deterministic -- same demo data every fresh run

    # --- Employees --------------------------------------------------------
    employee_specs = [
        ("Jake Morgan", EmployeeRole.MANAGER),
        ("Maya Patel", EmployeeRole.MANAGER),
        ("Alex Carter", EmployeeRole.TECHNICIAN),
        ("Jordan Lee", EmployeeRole.TECHNICIAN),
        ("Chris Miller", EmployeeRole.EQUIPMENT_OPERATOR),
        ("Taylor Brooks", EmployeeRole.TECHNICIAN),
        ("Sam Wilson", EmployeeRole.SITE_WORKER),
        ("Priya Shah", EmployeeRole.TECHNICIAN),
        ("Ethan Davis", EmployeeRole.EQUIPMENT_OPERATOR),
        ("Olivia Reed", EmployeeRole.SITE_WORKER),
    ]
    employees: dict[str, Employee] = {}
    for name, role in employee_specs:
        emp = Employee(name=name, role=role, active=True, created_at=now)
        db.add(emp)
        employees[name] = emp
    db.flush()

    # --- Projects -----------------------------------------------------------
    project_specs = [
        ("House #1", "Jake Morgan", ProjectStatus.ACTIVE, -30, 60),
        ("Mall Construction #4", "Maya Patel", ProjectStatus.ACTIVE, -60, 150),
        ("Office Renovation #2", "Jake Morgan", ProjectStatus.ACTIVE, -20, 40),
        ("Warehouse Expansion #3", "Maya Patel", ProjectStatus.ACTIVE, -45, 90),
        ("Apartment Build #7", "Jake Morgan", ProjectStatus.PLANNING, 14, 220),
        ("Community Center #5", "Maya Patel", ProjectStatus.ACTIVE, -15, 75),
        ("Riverside Bridge Repair #8", "Jake Morgan", ProjectStatus.ON_HOLD, -90, 30),
        ("Retail Plaza #9", "Maya Patel", ProjectStatus.COMPLETED, -200, -10),
    ]
    projects: dict[str, Project] = {}
    for name, manager_name, status, start_offset, end_offset in project_specs:
        proj = Project(
            name=name,
            status=status,
            manager_id=employees[manager_name].id,
            start_date=(now + timedelta(days=start_offset)).date(),
            expected_end_date=(now + timedelta(days=end_offset)).date(),
            location=name,
            created_at=now + timedelta(days=start_offset),
        )
        db.add(proj)
        projects[name] = proj
    db.flush()
    for proj in projects.values():
        log_activity(
            db,
            ActivityEventType.PROJECT_CREATED,
            f"Project {proj.name} created.",
            project_id=proj.id,
        )
    db.flush()

    team_specs = [
        ("House #1", ["Alex Carter", "Chris Miller", "Priya Shah"]),
        ("Mall Construction #4", ["Ethan Davis", "Jordan Lee", "Taylor Brooks", "Sam Wilson"]),
        ("Office Renovation #2", ["Alex Carter", "Olivia Reed"]),
        ("Warehouse Expansion #3", ["Chris Miller", "Ethan Davis", "Jordan Lee", "Taylor Brooks"]),
        ("Community Center #5", ["Priya Shah", "Sam Wilson", "Olivia Reed"]),
    ]
    for proj_name, member_names in team_specs:
        for member in member_names:
            db.add(
                ProjectEmployee(
                    project_id=projects[proj_name].id,
                    employee_id=employees[member].id,
                    assigned_at=now,
                )
            )
    db.flush()

    # --- Equipment ------------------------------------------------------------
    # (name, type, interval_hours, max_usage_count)
    equipment_specs: list[tuple[str, str, int, "int | None"]] = []

    def add_numbered(prefix: str, type_: str, count: int, interval: int, max_usage=None):
        for i in range(1, count + 1):
            equipment_specs.append((f"{prefix} #{i:02d}", type_, interval, max_usage))

    add_numbered("Cordless Drill", "drill", 3, 400)
    add_numbered("Impact Driver", "drill", 2, 400)
    add_numbered("Circular Saw", "saw", 3, 350)
    add_numbered("Angle Grinder", "grinder", 3, 300)
    add_numbered("Concrete Mixer", "mixer", 2, 500)
    add_numbered("Generator", "generator", 3, 600)
    add_numbered("Water Pump", "pump", 2, 450)
    add_numbered("Air Compressor", "compressor", 2, 550)
    add_numbered("Welding Machine", "welder", 2, 500)
    add_numbered("Nail Gun", "nail gun", 2, 300)
    add_numbered("Pressure Washer", "washer", 1, 400)
    add_numbered("Extension Reel", "electrical", 2, 800)
    add_numbered("Ladder", "ladder", 2, 1000)
    add_numbered("Safety Harness", "safety", 6, 9999, max_usage=50)
    add_numbered("Rotary Hammer", "hammer", 2, 350)
    add_numbered("Demolition Hammer", "hammer", 1, 300)
    add_numbered("Tile Cutter", "cutter", 1, 400)
    add_numbered("Shop Vacuum", "vacuum", 2, 500)
    add_numbered("Plate Compactor", "compactor", 1, 450)
    add_numbered("Laser Level", "measuring", 2, 1200)

    equipment: dict[str, Equipment] = {}
    for name, type_, interval, max_usage in equipment_specs:
        # Bulk variety: most equipment sits comfortably under its interval,
        # a handful lands past it (overdue) or just under (due soon) --
        # this is what gives the dashboard's overdue list its baseline
        # count without every single item needing a scripted backstory.
        roll = rng.random()
        if roll < 0.10:
            fraction_of_interval = rng.uniform(1.02, 1.3)  # overdue
        elif roll < 0.25:
            fraction_of_interval = rng.uniform(0.82, 0.98)  # due soon
        else:
            fraction_of_interval = rng.uniform(0.05, 0.75)  # healthy
        usage_hours = Decimal(str(round(interval * fraction_of_interval, 1)))
        usage_count = rng.randint(0, max_usage - 3) if max_usage else 0

        eq = Equipment(
            name=name,
            type=type_,
            location=HOME_LOCATION,
            current_location=HOME_LOCATION,
            status=EquipmentStatus.OPERATIONAL,
            usage_hours=usage_hours,
            last_maintenance_usage_hours=Decimal("0"),
            maintenance_interval_hours=Decimal(str(interval)),
            usage_count=usage_count,
            max_usage_count=max_usage,
        )
        db.add(eq)
        equipment[name] = eq
    db.flush()

    # --- Parts ------------------------------------------------------------
    # (name, unit_cost)
    part_specs = [
        ("Drill Bits", Decimal("4.50")), ("Saw Blades", Decimal("12.00")),
        ("Grinding Discs", Decimal("3.25")), ("Drive Belts", Decimal("18.00")),
        ("Bearings", Decimal("6.75")), ("Oil Filters", Decimal("9.00")),
        ("Air Filters", Decimal("7.50")), ("Spark Plugs", Decimal("2.80")),
        ("Hex Bolts", Decimal("0.20")), ("Wood Screws", Decimal("0.10")),
        ("Concrete Anchors", Decimal("0.65")), ("Safety Anchors", Decimal("3.40")),
        ("Electrical Cable", Decimal("1.20")), ("Fuses", Decimal("0.45")),
        ("Hydraulic Hoses", Decimal("22.00")), ("Lubricant", Decimal("11.00")),
        ("Hydraulic Fluid", Decimal("15.50")), ("Replacement Chains", Decimal("28.00")),
        ("Power Tool Batteries", Decimal("45.00")), ("O-Ring Seals", Decimal("1.10")),
        ("Assorted Fasteners", Decimal("0.15")), ("Cutting Discs", Decimal("4.00")),
        ("Welding Tips", Decimal("6.20")), ("Hose Clamps", Decimal("1.75")),
        ("Safety Glasses", Decimal("5.00")), ("Work Gloves", Decimal("8.50")),
        ("Ear Protection", Decimal("6.00")), ("Respirator Filters", Decimal("8.00")),
        ("Zip Ties", Decimal("0.05")), ("Duct Tape", Decimal("6.50")),
        ("Tarps", Decimal("14.00")), ("Extension Cords", Decimal("19.00")),
        ("Gas Cans", Decimal("16.00")), ("PVC Fittings", Decimal("2.10")),
        ("Copper Fittings", Decimal("3.60")), ("Rebar Ties", Decimal("0.08")),
        ("Silicone Sealant", Decimal("5.75")), ("Tape Measures", Decimal("13.00")),
        ("Marking Chalk", Decimal("3.00")), ("Sandpaper", Decimal("0.90")),
    ]
    # Explicit low/near-threshold stock for the parts the demo specifically
    # calls out; everything else gets varied-but-healthy stock.
    forced_stock = {
        "Grinding Discs": (3, 5, False),
        "Drive Belts": (1, 3, False),
        "Oil Filters": (4, 5, False),
        "Respirator Filters": (2, 5, True),
        "Safety Glasses": (6, 8, True),
        # 100/85: the exact numbers from the spec's worked example --
        # consumed down to 80 by the Wood Screws use_parts_on_project call
        # below, crossing the threshold live rather than starting there.
        "Wood Screws": (100, 85, False),
    }

    parts: dict[str, Part] = {}
    for name, unit_cost in part_specs:
        if name in forced_stock:
            qty, threshold, critical = forced_stock[name]
        else:
            threshold = rng.choice([5, 8, 10, 15])
            qty = threshold + rng.randint(5, 80)
            critical = rng.random() < 0.12
        part = Part(
            name=name,
            sku=f"{name[:3].upper()}-{rng.randint(100, 999)}",
            quantity_on_hand=qty,
            reorder_threshold=threshold,
            unit_cost=unit_cost,
            is_critical=critical,
        )
        db.add(part)
        parts[name] = part
    db.flush()

    # --- Scripted scenarios (go through real logic.py functions) ------------

    # Concrete Mixer #01: overdue for maintenance, sitting at home.
    equipment["Concrete Mixer #01"].usage_hours = Decimal("523.0")
    equipment["Concrete Mixer #01"].last_maintenance_usage_hours = Decimal("0")

    # Safety Harness #02: right at its wear limit via a real checkout, so it
    # shows up in discard-recommended *and* the activity feed explains why.
    equipment["Safety Harness #02"].usage_count = 49
    loan = check_out_equipment(
        db,
        equipment_id=equipment["Safety Harness #02"].id,
        project_id=projects["House #1"].id,
        borrower_employee_id=employees["Priya Shah"].id,
        expected_return_at=now + timedelta(days=2),
    )
    return_equipment(db, loan.id)  # returned, but the 50th use already tripped the flag

    # Safety Harness #06: currently out on House #1, usage climbing toward
    # (not at) the limit.
    equipment["Safety Harness #06"].usage_count = 46
    check_out_equipment(
        db,
        equipment_id=equipment["Safety Harness #06"].id,
        project_id=projects["House #1"].id,
        borrower_employee_id=employees["Alex Carter"].id,
        expected_return_at=now + timedelta(days=3),
    )

    # Cordless Drill #03: out on House #1, due back soon.
    check_out_equipment(
        db,
        equipment_id=equipment["Cordless Drill #03"].id,
        project_id=projects["House #1"].id,
        borrower_employee_id=employees["Alex Carter"].id,
        expected_return_at=now + timedelta(days=1),
    )

    # Generator #02: out on Mall Construction #4, maintenance due soon
    # (not yet overdue).
    equipment["Generator #02"].usage_hours = Decimal("505.0")
    equipment["Generator #02"].last_maintenance_usage_hours = Decimal("0")
    check_out_equipment(
        db,
        equipment_id=equipment["Generator #02"].id,
        project_id=projects["Mall Construction #4"].id,
        borrower_employee_id=employees["Ethan Davis"].id,
        expected_return_at=now + timedelta(hours=20),  # due tomorrow
    )

    # A few more active checkouts across other projects for a fuller
    # "equipment by location" and "due soon" picture.
    more_checkouts = [
        ("Circular Saw #02", "House #1", "Chris Miller", 4),
        ("Angle Grinder #01", "Mall Construction #4", "Jordan Lee", 6),
        ("Welding Machine #01", "Warehouse Expansion #3", "Chris Miller", 5),
        ("Ladder #01", "Office Renovation #2", "Olivia Reed", 2),
        ("Air Compressor #01", "Community Center #5", "Sam Wilson", 7),
    ]
    for eq_name, proj_name, emp_name, days in more_checkouts:
        check_out_equipment(
            db,
            equipment_id=equipment[eq_name].id,
            project_id=projects[proj_name].id,
            borrower_employee_id=employees[emp_name].id,
            expected_return_at=now + timedelta(days=days),
        )

    # A returned loan (history, not just active state).
    returned_loan = check_out_equipment(
        db,
        equipment_id=equipment["Rotary Hammer #01"].id,
        project_id=projects["Retail Plaza #9"].id,
        borrower_employee_id=employees["Taylor Brooks"].id,
        expected_return_at=now - timedelta(days=5),
    )
    return_equipment(db, returned_loan.id)

    # Maintenance history: a couple of completed jobs, one of which is the
    # "just serviced" reason a few items are healthy despite heavy use.
    record_maintenance(
        db,
        equipment_id=equipment["Concrete Mixer #02"].id,
        performed_at=now - timedelta(days=10),
        description="Routine service -- oil and filter change.",
        parts_used=[PartUsageInput(part_id=parts["Oil Filters"].id, quantity=1)],
    )
    record_maintenance(
        db,
        equipment_id=equipment["Generator #01"].id,
        performed_at=now - timedelta(days=3),
        description="Replaced spark plugs and air filter.",
        parts_used=[
            PartUsageInput(part_id=parts["Spark Plugs"].id, quantity=2),
            PartUsageInput(part_id=parts["Air Filters"].id, quantity=1),
        ],
    )

    # Restock history -- deliberately not on any part in forced_stock, so a
    # restock here can't accidentally undo a scripted low-stock scenario.
    restock_part(db, part_id=parts["Concrete Anchors"].id, quantity=150, unit_cost=Decimal("0.65"), supplier="BuildRight Distributors")
    restock_part(db, part_id=parts["Hex Bolts"].id, quantity=500, unit_cost=Decimal("0.20"), supplier="Acme Supply Co")

    # Project part usage -- consumes Wood Screws below its reorder
    # threshold (100 -> 80, threshold 85), the exact scenario from the spec.
    use_parts_on_project(
        db,
        project_id=projects["House #1"].id,
        employee_id=employees["Alex Carter"].id,
        parts_used=[PartUsageInput(part_id=parts["Wood Screws"].id, quantity=20)],
    )
    use_parts_on_project(
        db,
        project_id=projects["Mall Construction #4"].id,
        employee_id=employees["Jordan Lee"].id,
        parts_used=[
            PartUsageInput(part_id=parts["Electrical Cable"].id, quantity=15),
            PartUsageInput(part_id=parts["Hex Bolts"].id, quantity=40),
        ],
    )
    use_parts_on_project(
        db,
        project_id=projects["Office Renovation #2"].id,
        employee_id=employees["Olivia Reed"].id,
        parts_used=[PartUsageInput(part_id=parts["Drill Bits"].id, quantity=6)],
    )

    db.flush()
