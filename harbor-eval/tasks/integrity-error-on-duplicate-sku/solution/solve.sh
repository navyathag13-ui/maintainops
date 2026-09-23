#!/bin/bash
set -eu

cd /app

python3 - <<'PYEOF'
import re

path = "app/main.py"
src = open(path).read()

if "from sqlalchemy.exc import IntegrityError" not in src:
    src = src.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\nfrom sqlalchemy.exc import IntegrityError\n",
        1,
    )

handler = '''

# Catches what the typed logic.py exceptions above don't: a duplicate SKU,
# or deleting a part that still has maintenance history referencing it.
# Without this, either surfaces as a raw 500 with a stack trace -- the
# thing this app's error handling is otherwise careful to never do.
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "This request conflicts with existing data (e.g. a duplicate value, "
            "or a record that's still referenced elsewhere)."
        },
    )
'''

marker = "app.include_router(equipment.router)"
if "integrity_error_handler" not in src:
    src = src.replace(marker, handler.strip("\n") + "\n\n\n" + marker, 1)

open(path, "w").write(src)
PYEOF

echo "Applied: registered an IntegrityError exception handler returning a clean 409 JSON response."
