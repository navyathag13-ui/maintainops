# Bug report: negative/zero values accepted for fields that should never be negative

This is a FastAPI + SQLAlchemy backend for an equipment/parts maintenance tracker. The app's source lives in `/app/app`.

**Symptom:** Several numeric fields that should never be negative (or, in a couple of cases, should never be zero) are accepted without validation by the API. A client can drive stock counts, costs, or usage numbers negative, silently corrupting inventory and reporting.

**Steps to reproduce:**
1. Create a part via `POST /parts/`.
2. `PATCH /parts/{id}` with `{"quantity_on_hand": -5}`.
3. Observe: the request succeeds (200) and the part's `quantity_on_hand` is now `-5` in the database, instead of being rejected.

The same problem affects other fields across parts and equipment — e.g. `unit_cost`, `reorder_threshold` on parts, and `usage_hours`, `maintenance_interval_hours`, `max_usage_count` on equipment (interval and max-usage-count should be strictly positive, not just non-negative).

**Expected behavior:** These fields should reject invalid values with a 422 Unprocessable Entity, the same way this app's schemas already validate other fields (e.g. part restock quantity already correctly requires a positive value).

Fix the schemas so all of these fields are properly constrained, both on creation and on partial update (PATCH).
