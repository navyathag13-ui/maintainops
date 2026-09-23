# Bug report: duplicate SKU crashes the server instead of returning an error

This is a FastAPI + SQLAlchemy backend for an equipment/parts maintenance tracker. The app's source lives in `/app/app`. It's meant to always return clean JSON error responses (4xx) for expected failure conditions — never a raw, unhandled 500.

**Symptom:** Creating a part with a SKU that already exists in the database does not return a normal error response. Instead the request fails with an unhandled server error (HTTP 500, "Internal Server Error", no useful detail in the body).

**Steps to reproduce:**
1. `POST /parts/` with a JSON body containing a `sku` value (e.g. `{"name": "Wrench", "sku": "DUP1", "quantity_on_hand": 5, "reorder_threshold": 1, "unit_cost": "10.00"}`) — this succeeds.
2. `POST /parts/` again with the same `sku` value.
3. Observe: the second request returns HTTP 500 with no structured error detail, instead of a clear 4xx JSON error explaining the conflict.

**Expected behavior:** The second request should fail cleanly with a 4xx JSON response describing the conflict (e.g. "duplicate SKU"), consistent with how every other foreseeable failure in this app is handled.

Fix the underlying issue so that this class of database-integrity conflict (not just this one specific case) is handled cleanly and returns a proper JSON error response instead of crashing.
