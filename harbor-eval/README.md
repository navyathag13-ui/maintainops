# Harbor evaluation: can Claude Code autonomously fix MaintainOps' real bugs?

This directory measures whether Claude Code, driven autonomously through the
[Harbor](https://github.com/harbor-framework/harbor) evaluation framework, can
fix the real defects a four-reviewer audit of this codebase found and fixed in
commit [`edefd22`](../../../commit/edefd22) ("Fix 8 real bugs found by a
full-codebase review").

Full methodology and results live in [`results.md`](results.md).

## Status

- **Phase 0 (environment setup): done.** Harbor installed via `uv` (Python 3.13);
  Docker Desktop provides the sandbox; Claude Code runs as the agent under test,
  authenticated with a Claude subscription token (`CLAUDE_FORCE_OAUTH=1`).

- **Phase 1 (task reconstruction): done.** 5 tasks covering 4 of the 9 fixes itemized in
  `edefd22` (the delete-guard fix became two tasks) were turned into real, verified Harbor tasks (see `tasks/`
  below). Each one's "buggy" environment was built by taking the *current*
  backend (which already includes all 9 original fixes plus everything since)
  and reverse-applying only that one fix — not by rolling back to the old
  commit, so nothing from later work (Projects/Employees/dashboard/etc.) is
  lost. Every reconstruction and every verifier was locally confirmed:
  - The verifier **fails** against the reconstructed buggy code.
  - The verifier **passes** against the real, current (fixed) codebase.
  - A `solution/solve.sh` reference fix, reverse-derived from the same
    `edefd22` diff, independently turns the verifier green.

- **Phase 2 (run Claude Code against each task): done** — 5/5 tasks fixed on all 3 attempts (15/15 runs), see `results.md`.
- **Phase 3 (TTFT/throughput): done** — `scripts/extract_metrics.py`; ITL isn't directly measurable.
- **Phase 4 (results.md + integration): done.**

## The 5 reconstructed tasks

| Task | Difficulty | Original fix |
|---|---|---|
| `integrity-error-on-duplicate-sku` | easy | Missing `IntegrityError` exception handler — duplicate SKU crashed with a raw 500 |
| `negative-value-validation` | easy | Missing Pydantic `ge=0`/`gt=0` constraints let PATCH drive stock/cost/hours negative |
| `delete-part-with-history-crash` | medium | Composite-PK FK cascade threw an uncaught `AssertionError` on delete instead of a clean 409 |
| `delete-checked-out-equipment-loses-loan` | medium | Deleting checked-out equipment silently cascade-deleted the active loan record |
| `record-maintenance-lock-ordering` | hard (concurrency) | `record_maintenance` locked `Part` rows in client-supplied order, risking a Postgres deadlock under concurrent requests |

## Which fixes became tasks

`edefd22`'s commit message itemizes 9 fixes (6 backend, 3 frontend). Four of them became the five tasks above (the delete-guard fix became two tasks), chosen because each has a single clean, pytest-verifiable symptom. The other five are natural next tasks:

- **`return_equipment` missing an `Equipment` lock, and `update_equipment`/`update_part` PATCH reading via an unlocked `db.get()`.** These are the same kind of defect as `record-maintenance-lock-ordering` (a missing `SELECT ... FOR UPDATE`), so they would add more concurrency tasks; they are good candidates for a second wave that checks whether the agent generalizes the lock-ordering lesson.
- **The 3 frontend bugs** (Toast's stale-closure timer, an un-awaited `handleReturn` creating a double-return race, `RestockForm`'s stale price on remount). They need a browser-level verifier (Vitest) instead of pytest, and they already have Vitest regression tests in the app itself (`frontend/src/**/*.test.tsx`), which makes them ready to wrap as tasks.

The guiding idea: a task should isolate one defect cleanly, so five clean tasks came before nine forced ones.
