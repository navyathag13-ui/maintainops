# Results: Claude Code vs. MaintainOps' audited defects (Harbor)

Every number below comes from an actual Harbor run (Docker containers, Claude Code
agent, model `claude-sonnet-5`, one attempt per task, authenticated via a Claude
subscription token). Raw metrics: [`metrics.json`](metrics.json), produced by
[`scripts/extract_metrics.py`](scripts/extract_metrics.py).

## Headline

**Claude Code fixed 5 of 5 reconstructed defects autonomously** (verifier reward 1.0 on each),
given only the symptom-only `instruction.md`.

## Harness validation (done before the agent runs)

| Agent | Result on all 5 tasks |
|---|---|
| `nop` (does nothing) | reward 0.0 on 5/5 |
| `oracle` (reference fix) | reward 1.0 on 5/5 |

So a 1.0 means the bug was really fixed as judged by the verifier, and a task can't be
passed by doing nothing.

## Per-task results

| Task | Difficulty | Reward | TTFT (ms) | Turns | Output tokens | Wall time (s) | API time / output token (ms) | Output tok/s |
|---|---|---|---|---|---|---|---|---|
| integrity-error-on-duplicate-sku | easy | 1.0 | 1438 | 20 | 5721 | 58.7 | 9.8 | 102.3 |
| negative-value-validation | easy | 1.0 | 1084 | 7 | 2898 | 24.9 | 8.3 | 119.9 |
| delete-part-with-history-crash | medium | 1.0 | 3651 | 28 | 14115 | 158.8 | 10.9 | 91.6 |
| delete-checked-out-equipment-loses-loan | medium | 1.0 | 2875 | 23 | 5176 | 220.5 | 39.8 | 25.1 |
| record-maintenance-lock-ordering | hard | 1.0 | 1391 | 9 | 4867 | 45.8 | 9.3 | 107.2 |

How the columns are defined:
- **TTFT** is Claude Code's own `ttft_ms` field (time to first token of the run's first model call).
- **Turns, output tokens, wall time** are from Claude Code's final result record. Wall time is the agent
  session only, not container build or verification.
- **Throughput** is output tokens divided by API time.
- **ITL is not directly measured.** Claude Code's log has no per-token timestamps, so a true
  inter-token latency can't be computed from it. "API time per output token" is a coarse stand-in
  that also includes thinking time and network overhead. Do not quote it as ITL.

## Harder vs. simpler defects

The expected pattern (concurrency bug is slowest) did **not** appear:
- The "hard" concurrency task was one of the fastest: 9 turns, 45.8 s.
- The most effort went to `delete-part-with-history-crash` (medium): 28 turns, 14k output tokens.
- `delete-checked-out-equipment-loses-loan` has the slowest wall time and lowest throughput, but its
  log shows an API retry and two sub-agent tasks, so its 25 tok/s reflects that overhead, not a
  property of the bug.
- TTFT was 1.1 to 1.4 s on the three lighter runs and 2.9 to 3.7 s on the two longer ones.

## What this does and doesn't show

Five tasks, one attempt each, one model, on a codebase the model may partly know (the fixes are a
public pattern), is a small sample. It shows Claude Code can fix these particular well-described
bugs end to end. It does not support a pass-rate claim, a difficulty ranking, or a latency
comparison between bug types: with n=1 per task, the differences above could be run-to-run noise.
The bug reports also name the symptom clearly, and several verifiers check behaviour (a 4xx instead of
a 500) rather than one specific fix, which makes them friendlier than an open-ended audit. The
lock-ordering verifier checks statement order on SQLite, not a real Postgres deadlock. I did not
audit the agent transcripts for shortcuts beyond the verifier's result. Timing came from a
subscription-authenticated session, so rate limits could have affected it (the logs contain
`rate_limit_event` entries).

One earlier attempt at the first task scored 0 because of a wrong model-name flag
(`anthropic/claude-sonnet-5` was rejected by the CLI). That was a configuration error, not a failed
fix, and it is excluded from the numbers above.

## Reproduce

```bash
harbor run -p harbor-eval/tasks/<task> -a claude-code -m claude-sonnet-5   # with CLAUDE_FORCE_OAUTH=1 + CLAUDE_CODE_OAUTH_TOKEN, or ANTHROPIC_API_KEY
python harbor-eval/scripts/extract_metrics.py <jobs dir> <5 job names in task order>
```
