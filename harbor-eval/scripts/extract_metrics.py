"""Extract Claude Code latency/throughput metrics from Harbor job dirs.

Usage: python extract_metrics.py <harbor jobs dir> [job names in task order]
Reads each trial's agent/claude-code.txt (stream-json) and result.json reward.
TTFT comes from Claude Code's own `ttft_ms` field. The stream has no per-token
timestamps, so true ITL is not measurable here; we report mean API time per
output token (duration_api_ms / output_tokens) as a coarse proxy.
"""
import glob, json, sys, os

TASKS = ["integrity-error-on-duplicate-sku", "negative-value-validation",
         "delete-part-with-history-crash", "delete-checked-out-equipment-loses-loan",
         "record-maintenance-lock-ordering"]

def main(jobs_dir, jobs):
    rows = []
    for task, job in zip(TASKS, jobs):
        log = glob.glob(os.path.join(jobs_dir, job, "*", "agent", "claude-code.txt"))[0]
        res = None
        for line in open(log):
            if line.startswith("{"):
                try: e = json.loads(line)
                except ValueError: continue
                if e.get("type") == "result": res = e
        reward = json.load(open(os.path.join(jobs_dir, job, "result.json")))["stats"]["evals"]
        reward = next(iter(reward.values()))["metrics"][0]["mean"]
        out = res["usage"]["output_tokens"]
        api = res["duration_api_ms"]
        rows.append({"task": task, "reward": reward, "ttft_ms": res["ttft_ms"],
                     "turns": res["num_turns"], "output_tokens": out,
                     "duration_ms": res["duration_ms"], "duration_api_ms": api,
                     "ms_per_output_token": round(api / out, 2),
                     "output_tokens_per_sec": round(out / (api / 1000), 1)})
    print(json.dumps(rows, indent=2))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
