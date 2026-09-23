# Incident note: intermittent deadlocks recording maintenance logs under concurrent load

This is a FastAPI + SQLAlchemy backend for an equipment/parts maintenance tracker, running against PostgreSQL in production. The app's source lives in `/app/app`.

**Symptom:** Under concurrent load, `POST /maintenance-logs` occasionally fails with a database deadlock error. It only happens when a maintenance log references more than one part, and only under concurrency — it cannot be reproduced with a single request by hand. It seems to depend on the order in which different concurrent requests reference the same overlapping parts.

**Context:** `record_maintenance` (in `app/logic.py`) locks the `Part` rows it needs with `SELECT ... FOR UPDATE` before checking stock and consuming it, to prevent two concurrent logs from both passing a stock check on the same part before either commits. This part of the design is correct and should not change.

**What to investigate:** Why two concurrent multi-part maintenance logs that reference the same two parts, in opposite order, can deadlock each other on Postgres — and fix the root cause in how `record_maintenance` acquires its locks on `Part` rows, without changing the function's externally-observable behavior (stock validation, shortfall reporting, etc. must all still work exactly as before).
