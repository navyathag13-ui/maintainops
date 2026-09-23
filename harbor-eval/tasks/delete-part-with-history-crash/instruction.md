# Bug report: deleting a part with maintenance history crashes the server

This is a FastAPI + SQLAlchemy backend for an equipment/parts maintenance tracker. The app's source lives in `/app/app`. It's meant to always return clean JSON error responses (4xx) for expected failure conditions — never a raw, unhandled 500.

**Symptom:** `DELETE /parts/{id}` works fine for a part that has never been used. But if the part has ever been consumed in a maintenance log (i.e. it has usage/cost history attached to it), the delete request crashes with an unhandled HTTP 500 instead of returning a normal error response.

**Steps to reproduce:**
1. Create a part via `POST /parts/`.
2. Create equipment via `POST /equipment/`.
3. Record a maintenance log that consumes the part: `POST /maintenance-logs` with `{"equipment_id": <id>, "performed_at": "...", "description": "...", "parts_used": [{"part_id": <id>, "quantity": 1}]}`.
4. `DELETE /parts/{id}` on that same part.
5. Observe: HTTP 500, no structured error detail.

**Expected behavior:** Deleting a part that has maintenance history should be refused with a clear 4xx JSON error (e.g. "part has maintenance history and can't be deleted"), not crash the server.

Fix the underlying issue so this is handled cleanly.
