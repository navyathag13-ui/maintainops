#!/bin/bash
set -eu

cd /app

python3 - <<'PYEOF'
path = "app/schemas.py"
src = open(path).read()

replacements = [
    ('usage_hours: Decimal = Decimal("0")', 'usage_hours: Decimal = Field(default=Decimal("0"), ge=0)'),
    ('maintenance_interval_hours: Decimal\n', 'maintenance_interval_hours: Decimal = Field(gt=0)\n'),
    ('max_usage_count: Optional[int] = None', 'max_usage_count: Optional[int] = Field(default=None, gt=0)'),
    ('usage_hours: Optional[Decimal] = None', 'usage_hours: Optional[Decimal] = Field(default=None, ge=0)'),
    ('maintenance_interval_hours: Optional[Decimal] = None',
     'maintenance_interval_hours: Optional[Decimal] = Field(default=None, gt=0)'),
    ('quantity_on_hand: int = 0', 'quantity_on_hand: int = Field(default=0, ge=0)'),
    ('reorder_threshold: int = 0', 'reorder_threshold: int = Field(default=0, ge=0)'),
    ('unit_cost: Decimal\n', 'unit_cost: Decimal = Field(ge=0)\n'),
    ('quantity_on_hand: Optional[int] = None', 'quantity_on_hand: Optional[int] = Field(default=None, ge=0)'),
    ('reorder_threshold: Optional[int] = None', 'reorder_threshold: Optional[int] = Field(default=None, ge=0)'),
    ('unit_cost: Optional[Decimal] = None', 'unit_cost: Optional[Decimal] = Field(default=None, ge=0)'),
]

for old, new in replacements:
    if old in src:
        src = src.replace(old, new)

open(path, "w").write(src)
PYEOF

echo "Applied: restored ge=0/gt=0 Pydantic Field constraints across EquipmentBase/Update and PartBase/Update."
