# Results: Claude Code vs. MaintainOps' audited defects (Harbor)

## Status: task construction complete, Claude Code runs NOT yet executed

No Claude Code pass/fail, TTFT, ITL or throughput numbers exist yet, so none are reported here.
The sandbox this was built in had no Docker (or alternative container runtime) and no
`ANTHROPIC_API_KEY`, both required by Harbor to run an agent against a task container.

## What was verified (real, locally reproduced)

For each of the 5 tasks (see `README.md`), using the Python 3.11 backend environment:

| Task | Verifier vs. buggy code | Verifier vs. current fixed code | Reference solve.sh makes it pass |
|---|---|---|---|
| integrity-error-on-duplicate-sku | fails (500) | passes | yes |
| negative-value-validation | fails (8 of 10 checks) | passes | yes |
| delete-part-with-history-crash | fails (500) | passes | yes |
| delete-checked-out-equipment-loses-loan | fails (204, loan lost) | passes | yes |
| record-maintenance-lock-ordering | fails (locks [2,1]) | passes | yes |

This shows the tasks are fair and discriminating. It says nothing about Claude Code's ability.

## Verified inside real Harbor + Docker containers

| Agent | Result on all 5 tasks |
|---|---|
| `oracle` (applies reference fix) | reward 1.0 on 5/5 |
| `nop` (does nothing) | reward 0.0 on 5/5 |

So the Dockerfiles, `test.sh` scripts and verifiers work under Harbor: unfixed = fail, fixed = pass.
These are harness checks, not Claude Code results.

## Known limitations

- The lock-ordering verifier checks the order of `SELECT ... FOR UPDATE` statements on SQLite.
  It does not reproduce a real Postgres deadlock.
- Only 5 of 9 documented fixes are covered (see README for why).

## To finish

1. Set `ANTHROPIC_API_KEY` (Docker is done).
2. `harbor run -p harbor-eval/tasks/<task> -a claude-code -m anthropic/<model>`.
3. Capture TTFT/ITL/throughput from the run trajectories and fill in this file.
