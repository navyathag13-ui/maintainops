#!/bin/bash
set -eu

cd /app

python3 - <<'PYEOF'
path = "app/routers/equipment.py"
src = open(path).read()

old = '''def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    db.delete(equipment)'''

new = '''def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equipment = _get_or_404(db, equipment_id)
    if any(loan.returned_at is None for loan in equipment.loans):
        # Someone currently has this checked out. Deleting it would cascade
        # away that loan record -- the borrower's outstanding checkout
        # would just vanish with no error, warning, or record it ever
        # needs returning.
        raise HTTPException(
            status_code=409,
            detail=f"Equipment {equipment_id} is currently checked out and can't be deleted.",
        )
    db.delete(equipment)'''

assert old in src, "expected buggy delete_equipment body not found"
src = src.replace(old, new, 1)
open(path, "w").write(src)
PYEOF

echo "Applied: block deleting equipment that has an active, unreturned loan, with a clean 409."
