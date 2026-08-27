# MaintainOps

Equipment maintenance tracking and spare-parts inventory for a small industrial operations
team, replacing a spreadsheet-based workflow. Built as a portfolio project.

![Equipment list, color-coded maintenance status](docs/screenshots/equipment-list.png)

## Overview

MaintainOps tracks a fleet of equipment, the parts consumed servicing it, and surfaces two
operational alerts a maintenance team actually needs day to day:

- **Which equipment is overdue for service** — based on usage hours, not calendar time
- **Which parts are low on stock** — based on a per-part reorder threshold

Logging a maintenance event is the core transaction: it records what was done, consumes the
parts used from inventory (validating stock first, rejecting the whole request if anything
would go negative), and resets the equipment's maintenance clock.

![Dashboard with overdue and low-stock alerts](docs/screenshots/dashboard.png)

## Tech Stack

| Layer          | Choice                                              |
| -------------- | ---------------------------------------------------- |
| Backend        | Python 3.11+, FastAPI                                |
| ORM            | SQLAlchemy 2.0 (sync)                                 |
| Database       | PostgreSQL (via Docker Compose)                       |
| Backend tests  | pytest                                                |
| Frontend       | React 19 + TypeScript, Vite, React Router             |
| Containers     | Docker Compose (Postgres + backend + frontend)        |
| API docs       | FastAPI's built-in Swagger UI / OpenAPI               |

## Architecture

```
maintainops/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── models.py        SQLAlchemy models: Equipment, Part, MaintenanceLog, PartUsed
│   │   ├── logic.py         Core business logic (see below) -- framework-agnostic
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── database.py      Engine, session factory, commit-on-success get_db()
│   │   ├── main.py          FastAPI app, CORS, exception -> HTTP mapping
│   │   └── routers/         equipment.py, parts.py, maintenance_logs.py, alerts.py
│   ├── tests/
│   │   └── test_logic.py    23 tests against the business logic layer
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/client.ts     Typed fetch wrapper, one function per endpoint
    │   ├── types.ts          TypeScript interfaces mirroring the API schemas
    │   ├── utils.ts          Maintenance-status thresholding, formatting helpers
    │   ├── components/       MaintenanceStatusBadge, LowStockBadge, StatCard, LogMaintenanceForm
    │   ├── pages/            DashboardPage, EquipmentListPage, EquipmentDetailPage, PartsPage
    │   └── App.tsx           Routing + nav
    └── Dockerfile
```

The business logic lives in `logic.py`, separated from the FastAPI routers: it takes a
SQLAlchemy `Session` and plain arguments, raises its own exception types
(`EquipmentNotFoundError`, `InsufficientStockError`, etc.), and never touches HTTP. The
router layer's only job is translating those exceptions into status codes. This is what
makes it possible to unit-test the logic with a plain SQLite session and zero HTTP
machinery.

## Core Business Logic

**Overdue-maintenance check** (usage-hours based, not calendar time):

```python
def is_equipment_overdue(equipment: Equipment) -> bool:
    hours_since_service = equipment.usage_hours - equipment.last_maintenance_usage_hours
    return hours_since_service >= equipment.maintenance_interval_hours
```

**Low-stock check:**

```python
def is_part_low_stock(part: Part) -> bool:
    return part.quantity_on_hand <= part.reorder_threshold
```

**Recording maintenance** (`record_maintenance`) is the one with real edge cases:

1. Validates every `parts_used` entry up front — positive quantity, no duplicate part in
   the same request — before touching the database.
2. Loads the equipment and every part with `SELECT ... FOR UPDATE`, so two concurrent
   maintenance logs against the same part can't both pass the stock check before either
   commits (a no-op on SQLite, which has no row-level locking, but real protection on the
   Postgres target).
3. Checks *all* parts against current stock before mutating *any* of them — a shortfall on
   one part out of five aborts the whole log with zero partial decrements, and the caller
   gets back exactly which parts were short and by how much.
4. On success: decrements each part's `quantity_on_hand`, creates the `MaintenanceLog` and
   its `PartUsed` rows, and resets `equipment.last_maintenance_usage_hours` to the
   equipment's current `usage_hours`.
5. Only `flush()`es, never `commit()`s — the caller (the FastAPI dependency in
   `database.py`) owns the transaction boundary and commits on success / rolls back on any
   exception.

**Data types**: `usage_hours`, `last_maintenance_usage_hours`, and
`maintenance_interval_hours` are `Numeric`, not `Float`. The overdue check is an exact `>=`
comparison against a value that accumulates from repeated updates — float rounding drift
could eventually put equipment on the wrong side of the threshold. `unit_cost` is `Numeric`
for the same reason money always is.

## API Reference

All endpoints return JSON. Errors are consistent JSON (`{"detail": "..."}`, with a
`shortfalls` array added for stock-insufficiency errors) — never a raw stack trace.

| Method | Endpoint                         | Description                                                |
| ------ | --------------------------------- | ------------------------------------------------------------ |
| GET    | `/equipment`                      | List all equipment                                            |
| POST   | `/equipment`                      | Create equipment                                               |
| GET    | `/equipment/{id}`                 | Get one piece of equipment                                     |
| PATCH  | `/equipment/{id}`                 | Partial update                                                 |
| DELETE | `/equipment/{id}`                 | Delete                                                          |
| GET    | `/equipment/{id}/history`         | Maintenance logs for this equipment, newest first               |
| GET    | `/parts`                          | List all parts                                                  |
| POST   | `/parts`                          | Create a part                                                    |
| GET    | `/parts/{id}`                     | Get one part                                                     |
| PATCH  | `/parts/{id}`                     | Partial update                                                   |
| DELETE | `/parts/{id}`                     | Delete                                                            |
| POST   | `/maintenance-logs`               | Log maintenance, consuming parts and resetting the baseline        |
| GET    | `/alerts/overdue-maintenance`     | Equipment currently overdue, with hours-overdue                     |
| GET    | `/alerts/low-stock`               | Parts at or below their reorder threshold                            |

Status codes: `404` for a missing equipment/part id, `400` for validation failures
(insufficient stock, invalid quantity, duplicate part in one request), `201` on create,
`204` on delete.

Interactive docs (Swagger UI) are at `/docs`, ReDoc at `/redoc` — both work standalone, with
no frontend running.

## Quick Start

### With Docker (recommended)

```bash
git clone https://github.com/navyathag13-ui/maintainops.git
cd maintainops
docker-compose up --build
```

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API + Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Postgres: `localhost:5432` (`maintainops` / `maintainops`)

### Running locally without Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Needs a running Postgres, or point DATABASE_URL at SQLite for a quick local check:
DATABASE_URL="sqlite:///./dev.db" uvicorn app.main:app --reload
```

Backend tests:

```bash
cd backend
pytest tests/ -v
```

Frontend:

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000
npm install
npm run dev
```

## Testing

`backend/tests/test_logic.py` — 23 pytest cases against the three business-logic functions,
run against a fresh in-memory SQLite database per test. Covers both correct paths and the
edge cases that actually matter for this domain:

- Exactly-at-threshold for both the overdue check and the low-stock check (spec says
  `>=` / `<=`, so the boundary itself needs a test, not just values on either side)
- Zero stock, and insufficient stock on one part out of a multi-part request (asserting the
  *other* part's quantity is untouched — proving the operation is all-or-nothing)
- Zero/negative requested quantity, and the same part listed twice in one request
- Equipment with no prior maintenance history (first-ever service)
- Unknown equipment id / unknown part id

## Design Decisions Worth Knowing About

- **`record_maintenance` doesn't commit.** It only `flush()`es. Committing is the FastAPI
  dependency's job (`get_db` in `database.py`, commit-on-success / rollback-on-exception).
  This keeps the logic layer transaction-agnostic and testable without a real HTTP request.
- **Row locking (`SELECT ... FOR UPDATE`) on the maintenance-log path.** Guards against two
  concurrent requests both passing the stock check before either commits. This has no effect
  under the SQLite test database (SQLite has no row-level locking), so it's verified by
  reasoning about the SQL generated, not by a concurrency test in this suite.
  Postgres, i.e. the real deployment target, honors it.
- **The maintenance status badge has three colors (green/yellow/red) in the UI, but the
  backend's `is_equipment_overdue` is a boolean.** "Due soon" (yellow) is a frontend-only
  presentation threshold — 80% of the maintenance interval elapsed since last service — not
  a backend concept. See `frontend/src/utils.ts`.
- **`parts_used` uses a composite primary key** `(maintenance_log_id, part_id)` rather than
  a surrogate id, so the database itself rejects a duplicate part in one log (on top of the
  application-level check in `record_maintenance`).
- **No migration tool.** At this project's scale, `Base.metadata.create_all()` on startup is
  enough. Alembic would be the next step if this grew.

## Future Improvements

- Alembic migrations once the schema needs to evolve without dropping data
- Auth (this is currently an open internal tool with no login)
- Pagination on `/equipment` and `/parts` once fleets/catalogs get large
- A dedicated `/dashboard/summary` endpoint if the two alert-count queries become a
  bottleneck (currently the frontend just takes `.length` of the two alert lists)
