# Bug report: deleting checked-out equipment silently destroys the active loan record

This is a FastAPI + SQLAlchemy backend for an equipment/parts maintenance tracker. The app's source lives in `/app/app`.

**Symptom:** `DELETE /equipment/{id}` succeeds even when that equipment is currently checked out on an active (unreturned) loan. When this happens, the equipment row is deleted and the outstanding loan record disappears along with it — with no error, warning, or trace that it ever needed to be returned. The borrower's checkout just silently vanishes from the system.

**Steps to reproduce:**
1. Create equipment via `POST /equipment/`, an employee via `POST /employees/`, and a project via `POST /projects/`.
2. Check the equipment out: `POST /equipment/{id}/checkout` with `{"project_id": ..., "borrower_employee_id": ..., "expected_return_at": "..."}`.
3. Confirm the loan exists: `GET /equipment-loans`.
4. `DELETE /equipment/{id}` on the checked-out equipment — this succeeds (204).
5. `GET /equipment-loans` again — the loan record is gone.

**Expected behavior:** Deleting equipment that has an active, unreturned loan should be refused with a clear 4xx error, not silently cascade-delete the loan.

Fix the underlying issue so this is handled cleanly.
