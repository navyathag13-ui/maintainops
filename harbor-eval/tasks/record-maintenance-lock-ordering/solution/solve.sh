#!/bin/bash
set -eu

cd /app

python3 - <<'PYEOF'
path = "app/logic.py"
src = open(path).read()

old = '''    parts_by_id: dict[int, Part] = {}
    shortfalls: list[StockShortfall] = []
    for usage in parts_used:
        part = db.execute(
            select(Part).where(Part.id == usage.part_id).with_for_update()
        ).scalar_one_or_none()
        if part is None:
            raise PartNotFoundError(usage.part_id)
        parts_by_id[usage.part_id] = part
        if part.quantity_on_hand < usage.quantity:
            shortfalls.append(
                StockShortfall(
                    part_id=usage.part_id,
                    requested=usage.quantity,
                    available=part.quantity_on_hand,
                )
            )'''

new = '''    parts_by_id: dict[int, Part] = {}
    shortfalls: list[StockShortfall] = []
    # Lock parts in a canonical (id) order, not client-supplied order --
    # two concurrent multi-part logs referencing the same parts in opposite
    # order would otherwise each hold one lock and wait on the other,
    # deadlocking on Postgres instead of one of them simply waiting.
    for part_id in sorted({usage.part_id for usage in parts_used}):
        part = db.execute(
            select(Part).where(Part.id == part_id).with_for_update()
        ).scalar_one_or_none()
        if part is None:
            raise PartNotFoundError(part_id)
        parts_by_id[part_id] = part

    for usage in parts_used:
        part = parts_by_id[usage.part_id]
        if part.quantity_on_hand < usage.quantity:
            shortfalls.append(
                StockShortfall(
                    part_id=usage.part_id,
                    requested=usage.quantity,
                    available=part.quantity_on_hand,
                )
            )'''

assert old in src, "expected buggy record_maintenance locking loop not found"
src = src.replace(old, new, 1)
open(path, "w").write(src)
PYEOF

echo "Applied: lock Part rows in sorted(part_id) canonical order instead of client-supplied order."
