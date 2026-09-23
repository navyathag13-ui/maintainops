# Harbor evaluation: can Claude Code autonomously fix MaintainOps' real bugs?

This directory measures whether Claude Code, driven autonomously through the
[Harbor](https://github.com/harbor-framework/harbor) evaluation framework, can
fix the real defects a four-reviewer audit of this codebase found and fixed in
commit [`edefd22`](../../../commit/edefd22) ("Fix 8 real bugs found by a
full-codebase review").

Full methodology, results, and honest caveats live in [`results.md`](results.md)
once Phase 2/3 (actually running the tasks) has happened. This README tracks
what's been done and what's still blocked.

## Status

- **Phase 0 (environment setup): done, with two open dependencies.**
  No Docker, Docker alternative, or Homebrew were available in the sandbox
  this evaluation was built in. Harbor itself was installed cleanly via `uv`
  (Python 3.13, no admin rights needed). Two things are still required before
  Phase 2 can run:
  1. A sandboxed execution backend (Docker Desktop, Apple's `container` CLI,
     or a cloud sandbox provider) — Harbor needs one to actually run agents
     against task containers.
  2. An `ANTHROPIC_API_KEY` — Harbor drives Claude Code as a subprocess and
     bills it per-token, separately from any Claude Code subscription.

- **Phase 1 (task reconstruction): done.** 5 of the 9 fixes documented in
  `edefd22` were turned into real, verified Harbor tasks (see `tasks/`
  below). Each one's "buggy" environment was built by taking the *current*
  backend (which already includes all 9 original fixes plus everything since)
  and reverse-applying only that one fix — not by rolling back to the old
  commit, so nothing from later work (Projects/Employees/dashboard/etc.) is
  lost. Every reconstruction and every verifier was locally confirmed:
  - The verifier **fails** against the reconstructed buggy code.
  - The verifier **passes** against the real, current (fixed) codebase.
  - A `solution/solve.sh` reference fix, reverse-derived from the same
    `edefd22` diff, independently turns the verifier green.

- **Phase 2 (run Claude Code against each task): done** — 5/5 fixed, see `results.md`.
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

## Why only 5 of the 9 documented fixes

`edefd22`'s commit message documents 9 distinct fixes (6 backend, 3 frontend).
Excluded from this task set, with reasons:

- **`return_equipment` missing an `Equipment` lock, and `update_equipment`/
  `update_part` PATCH reading via an unlocked `db.get()`.** Both are the same
  *kind* of defect as `record-maintenance-lock-ordering` (a missing
  `SELECT ... FOR UPDATE`), and would add redundant "hard" tasks rather than
  genuine diversity in what's being measured.
- **The 3 frontend bugs** (Toast's stale-closure timer, an un-awaited
  `handleReturn` creating a double-return race, `RestockForm`'s stale price on
  remount) are real, but verifying them needs a browser-level test stack
  (Vitest/Playwright), not pytest — a fundamentally different verifier
  approach from the other 5 tasks, and outside this first pass's scope.

This mirrors the instruction this evaluation was built under: don't force a
defect into a task if it can't be cleanly isolated — 5 clean tasks beat 9
forced ones.
