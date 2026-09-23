# What I actually ran, and what came out

Machine: Apple M4, 10 cores, 16 GB RAM, macOS 26.5.1, Docker Desktop 29.8.0 (arm64). Dates are 2026-09-23 unless noted.

## The full stack from a clean clone

Cloned the repo at commit `d1bbd8f` into a temporary folder and ran `docker compose up -d --build`. It exited 0, and all three services came up: `db` (healthy), `backend`, `frontend`.

- `GET /health` returned `{"status":"ok"}`
- `GET /equipment` returned 44 rows (the demo data seeds itself on first start)
- `GET /dashboard/summary` returned 200, and the frontend on port 5173 returned 200
- On the real PostgreSQL container: creating a part with an existing SKU returned HTTP 409 with a JSON message, and `PATCH /parts/{id}` with `quantity_on_hand: -5` returned HTTP 422
- The backend logs contained no tracebacks

Then `docker compose down -v` to clean up. Single run, Apple silicon only.

## Test counts (pytest, in-memory SQLite)

| Commit | Tests passing |
|---|---|
| `edefd22^` (just before the bug-hunt fixes) | 53 |
| `edefd22` (the fixes) | 53 |
| current `main` | 68 |

So the tests that existed when the review ran (53, not the 41 I had once written down) all passed and still missed the nine fixes.

## The lock-ordering deadlock on real PostgreSQL 16

`harbor-eval/scripts/postgres_deadlock_check.py` starts two transactions that log maintenance using the same two parts in opposite order, with a one-second pause after each part lock so they overlap.

- Old code: `{'T1': 'OperationalError: deadlock detected', 'T2': 'OK'}`
- Fixed code: `{'T1': 'OK', 'T2': 'OK'}`

One run each. The pause makes the overlap deliberate, so this shows the bug is real; it does not measure how often it would happen in production.

## Harbor runs

- Do-nothing agent: 0 out of 5 tasks fixed
- Reference solutions: 5 out of 5
- Claude Code (`claude-sonnet-5`), one attempt per task: 5 out of 5

Per-run numbers: [`../harbor-eval/results.md`](../harbor-eval/results.md) and `../harbor-eval/metrics.json`. Verifier output for buggy vs fixed code: `../harbor-eval/verification_pytest_output.txt`.

## Secrets check

The full history was searched for API keys, tokens and connection strings. Nothing found; only `frontend/.env.example` is tracked.

## Frontend tests (2026-09-23)

`npm test` (Vitest 5): 12 tests pass, covering the Toast countdown (including the re-render bug), the maintenance-level thresholds and the restock form's price reset. `tsc -b`, `npm run lint` (0 warnings) and `npm run build` all pass. Writing the tests also surfaced a lint warning in `Toast.tsx` (a ref written during render), which I fixed without changing behaviour.

## Not checked

- The three frontend bugs from the review were not turned into Harbor tasks, so an agent was never tried on them (they do have regression tests now)
