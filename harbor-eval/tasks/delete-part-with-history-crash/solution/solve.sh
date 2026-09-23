#!/bin/bash
set -eu

cd /app

python3 - <<'PYEOF'
path = "app/routers/parts.py"
src = open(path).read()

old = '''def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = _get_or_404(db, part_id)
    db.delete(part)'''

new = '''def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = _get_or_404(db, part_id)
    if part.usages:
        # part_id is part of PartUsed's composite primary key, so it can't
        # be nulled out the way a normal FK would on delete -- cascading
        # would mean silently destroying the cost history those rows
        # record (unit_cost_at_time snapshots this app otherwise goes out
        # of its way to keep accurate and permanent). Block it instead.
        raise HTTPException(
            status_code=409,
            detail=f"Part {part_id} has maintenance history and can't be deleted.",
        )
    db.delete(part)'''

assert old in src, "expected buggy delete_part body not found"
src = src.replace(old, new, 1)
open(path, "w").write(src)
PYEOF

echo "Applied: block deleting a part that has maintenance history, with a clean 409."
