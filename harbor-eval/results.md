# Results: Claude Code vs. MaintainOps' audited defects (Harbor)

Every number below comes from an actual Harbor run (Docker containers, Claude Code agent, model `claude-sonnet-5`, authenticated with a Claude subscription token). Raw data: [`attempts.json`](attempts.json) (all 15 attempts), [`metrics.json`](metrics.json) (the first attempt of each task), produced by [`scripts/summarize_attempts.py`](scripts/summarize_attempts.py) and [`scripts/extract_metrics.py`](scripts/extract_metrics.py).

## Headline

**Claude Code fixed all 5 reconstructed defects on all 3 attempts each: 15 of 15 runs scored 1.0**, given only the symptom-only `instruction.md` and judged by each task's verifier. None of the runs errored.

## Harness validation (done before any agent ran)

| Agent | Result on all 5 tasks |
|---|---|
| `nop` (does nothing) | reward 0.0 on 5/5 |
| `oracle` (reference fix) | reward 1.0 on 5/5 |

So a 1.0 means the verifier saw the bug fixed, and a task cannot be passed by doing nothing.

## Per-task results (3 attempts each)

| Task | Difficulty | Passed | Turns (median, range) | Wall time s (median, range) | Output tokens (median) | TTFT ms (median, range) |
|---|---|---|---|---|---|---|
| integrity-error-on-duplicate-sku | easy | 3/3 | 19 (13-20) | 67 (59-70) | 5721 | 1667 (1438-3200) |
| negative-value-validation | easy | 3/3 | 7 (6-7) | 25 (20-34) | 2711 | 1879 (1084-3896) |
| delete-part-with-history-crash | medium | 3/3 | 28 (22-35) | 158 (122-159) | 14115 | 1776 (1757-3651) |
| delete-checked-out-equipment-loses-loan | medium | 3/3 | 23 (19-24) | 95 (76-220) | 5953 | 2875 (1852-3993) |
| record-maintenance-lock-ordering | hard | 3/3 | 9 (8-9) | 32 (27-46) | 3360 | 1391 (1391-1550) |

How the columns are defined:
- **TTFT** is Claude Code's own `ttft_ms` field (time to first token of the run's first model call).
- **Turns, output tokens, wall time** come from Claude Code's final result record. Wall time is the agent session only, not container build or verification.
- **Inter-token latency is not reported.** Claude Code's log has no per-token timestamps, so it cannot be computed from this data. Dividing API time by output tokens gives only a coarse figure that includes thinking time and network overhead; it is in `metrics.json` for the first attempts and should not be read as ITL.

## What the repeats added

Running each task three times sharpened the picture. Time to first token for the same task ranged widely between attempts (1084 to 3993 ms overall, and 1084 to 3896 ms on `negative-value-validation` alone), which shows TTFT here mostly reflects service load at that moment, so it is best read as a range for the whole set (about 1.1 to 4.0 seconds) and not compared between tasks.

Effort was the steadier signal. The lock-ordering task took 8 to 9 turns on every attempt, the fastest and most consistent, even though I had labelled it "hard". The delete-part task took the most turns every time (22 to 35). So the amount of work the agent needed on these five tasks did not follow my difficulty labels, which is a useful thing to know before designing a larger set.

## Reading the results

Fifteen runs on five tasks with one model show that Claude Code reliably fixes these well-described bugs end to end. The bug reports name the symptom clearly, and several verifiers check behaviour (a 4xx instead of a 500) and not one specific fix, so this is the "clear bug report" scenario. The lock-ordering verifier checks statement order on SQLite; the real-Postgres check is separate (`scripts/postgres_deadlock_check.py`: the earlier code deadlocks, the fixed code does not).

Natural next steps for a broader picture: harder and vaguer bug reports, more models, the five remaining fixes from the review as new tasks, and a review of the agent transcripts beyond the verifier result. Durations came from a subscription-authenticated session that logged some `rate_limit_event` entries (and one API retry), so they are best read as approximate.

Setup note: the model is passed to Harbor as `claude-sonnet-5`, without a provider prefix.

## Reproduce

```bash
harbor run -p harbor-eval/tasks/<task> -a claude-code -m claude-sonnet-5 --job-name rep2-<task>   # with CLAUDE_FORCE_OAUTH=1 and CLAUDE_CODE_OAUTH_TOKEN, or ANTHROPIC_API_KEY
python harbor-eval/scripts/summarize_attempts.py <jobs dir> <5 first-attempt job names in task order>
```
