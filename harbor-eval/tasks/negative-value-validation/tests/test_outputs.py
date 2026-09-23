import pytest
from pydantic import ValidationError

from app.schemas import EquipmentUpdate, PartUpdate


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity_on_hand", -5),
        ("reorder_threshold", -1),
        ("unit_cost", -1),
    ],
)
def test_part_update_rejects_negative_values(field, value):
    with pytest.raises(ValidationError):
        PartUpdate(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("usage_hours", -1),
        ("maintenance_interval_hours", -1),
        ("maintenance_interval_hours", 0),
        ("max_usage_count", -1),
        ("max_usage_count", 0),
    ],
)
def test_equipment_update_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        EquipmentUpdate(**{field: value})


def test_part_update_still_accepts_valid_values():
    # A correct fix must not become so strict it rejects legitimate updates.
    PartUpdate(quantity_on_hand=10, reorder_threshold=2, unit_cost=5)


def test_equipment_update_still_accepts_valid_values():
    EquipmentUpdate(usage_hours=100, maintenance_interval_hours=50, max_usage_count=10)
