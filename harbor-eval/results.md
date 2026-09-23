# Results: Claude Code vs. MaintainOps' audited defects (Harbor)

## Status: task construction complete, agent runs NOT yet executed

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
These checks ran directly with pytest, not inside Harbor containers, so the Dockerfiles and
`test.sh` scripts are untested under Harbor itself.

## Known limitations

- The lock-ordering verifier checks the order of `SELECT ... FOR UPDATE` statements on SQLite.
  It does not reproduce a real Postgres deadlock.
- Only 5 of 9 documented fixes are covered (see README for why).

## To finish

1. Install Docker; set `ANTHROPIC_API_KEY`.
2. `harbor run -p harbor-eval/tasks/<task> -a oracle` (should score 1 for every task), then
   `-a claude-code -m anthropic/<model>`.
3. Capture TTFT/ITL/throughput from the run trajectories and fill in this file.
