"""Summarize repeated Claude Code attempts per Harbor task.

Attempt 1 jobs are the original timestamped jobs (passed on the command line in task order);
attempts 2+ are jobs named rep<N>-<task> in the same jobs directory.

Usage: python summarize_attempts.py <jobs dir> <5 attempt-1 job names in task order>
Writes attempts.json next to the harbor-eval README and prints a table.
"""
import glob, json, os, re, statistics, sys

TASKS = ["integrity-error-on-duplicate-sku", "negative-value-validation",
         "delete-part-with-history-crash", "delete-checked-out-equipment-loses-loan",
         "record-maintenance-lock-ordering"]


def read_job(jobs_dir, job):
    log = glob.glob(os.path.join(jobs_dir, job, "*", "agent", "claude-code.txt"))
    result = json.load(open(os.path.join(jobs_dir, job, "result.json")))
    evals = result["stats"]["evals"]
    if not evals:
        return None  # job still running
    ev = next(iter(evals.values()))
    reward = ev["metrics"][0]["mean"] if ev["n_trials"] and not ev.get("n_errors") else None
    res = None
    if log:
        for line in open(log[0]):
            if line.startswith("{"):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") == "result":
                    res = e
    if res is None:
        return {"job": job, "reward": reward, "errored": True}
    return {"job": job, "reward": reward, "errored": reward is None,
            "ttft_ms": res.get("ttft_ms"), "turns": res.get("num_turns"),
            "output_tokens": res["usage"]["output_tokens"], "duration_s": round(res["duration_ms"] / 1000, 1)}


def main(jobs_dir, first_jobs):
    out = {}
    for task, first in zip(TASKS, first_jobs):
        runs = [read_job(jobs_dir, first)]
        for path in sorted(glob.glob(os.path.join(jobs_dir, f"rep*-{task}"))):
            run = read_job(jobs_dir, os.path.basename(path))
            if run:
                runs.append(run)
        out[task] = runs
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "attempts.json"), "w"), indent=2)
    print(f"{'task':42} {'attempts':>8} {'passed':>7} {'errored':>8}  ttft ms (min-max)   turns (min-max)")
    for task, runs in out.items():
        scored = [r for r in runs if not r["errored"]]
        passed = sum(1 for r in scored if r["reward"] == 1.0)
        ttfts = [r["ttft_ms"] for r in scored if r.get("ttft_ms")]
        turns = [r["turns"] for r in scored if r.get("turns")]
        print(f"{task:42} {len(scored):>8} {passed:>7} {len(runs)-len(scored):>8}  {min(ttfts)}-{max(ttfts)}          {min(turns)}-{max(turns)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
