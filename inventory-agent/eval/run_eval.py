"""Evaluate the inventory agent against live MaintainOps data.

Expected answers are computed from the API at run time, not hard-coded, so
the eval stays correct if the seed data changes. Each case checks two things:
did the agent call the right tool, and does the answer contain the facts the
tool returned (or, for the trick questions, refuse instead of inventing).

    python eval/run_eval.py --model qwen2.5:3b --prompt v1 v2
Writes eval/results/<model>_<prompt>.json and prints a summary table.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inventory_agent.agent import build_agent  # noqa: E402
from inventory_agent.tools import _get  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def _num(x) -> str:
    """45 -> "45", 14.10 -> "14.1": how a person would write it."""
    f = float(x)
    return str(int(f)) if f == int(f) else f"{f:g}"


def build_cases() -> list[dict]:
    parts = _get("/parts")
    low = _get("/alerts/low-stock")
    overdue = _get("/alerts/overdue-maintenance")
    by_name = {p["name"]: p for p in parts}
    a, b = by_name["Drill Bits"], by_name["Saw Blades"]
    return [
        {"id": "low_stock_all", "q": "What are we running low on?",
         "tool": "list_low_stock_parts", "must": [p["name"] for p in low]},
        {"id": "overdue", "q": "What equipment is overdue for maintenance?",
         "tool": "list_overdue_equipment", "must": [e["name"] for e in overdue]},
        {"id": "overdue_hours", "q": f"How many hours overdue is {overdue[0]['name']}?",
         "tool": "list_overdue_equipment", "must": [_num(overdue[0]["hours_overdue"])]},
        {"id": "count_drill_bits", "q": "How many drill bits do we have?",
         "tool": "find_part", "must": [_num(a["quantity_on_hand"])]},
        {"id": "count_by_sku", "q": f"What is the stock level for SKU {b['sku']}?",
         "tool": "find_part", "must": [_num(b["quantity_on_hand"])]},
        {"id": "unknown_part", "q": "How many titanium unicorn bolts do we have?",
         "tool": "find_part", "refuse": r"\b(no|not|none|don't|do not|couldn't|could not|isn't)\b"},
        {"id": "write_request", "q": "Set the Drill Bits quantity to 100.",
         "tool": None, "refuse": r"(can't|cannot|can only|unable|not able|only read|in MaintainOps)"},
    ]


def score(case: dict, answer: str, tools_called: list[str]) -> dict:
    text = answer.lower()
    right_tool = case["tool"] is None or case["tool"] in tools_called
    if "refuse" in case:
        content_ok = re.search(case["refuse"], text) is not None
        missing = [] if content_ok else ["did not decline"]
    else:
        missing = [m for m in case["must"] if m.lower() not in text]
        content_ok = not missing
    return {"right_tool": right_tool, "content_ok": content_ok, "passed": right_tool and content_ok,
            "missing": missing}


def run(model: str, prompt: str) -> dict:
    rows = []
    for case in build_cases():
        agent = build_agent(prompt_version=prompt, model_id=model)  # fresh agent: no memory between cases
        started = time.perf_counter()
        result = agent(case["q"])
        seconds = time.perf_counter() - started
        usage = result.metrics.accumulated_usage
        tools_called = sorted(result.metrics.tool_metrics.keys())
        answer = str(result).strip()
        rows.append({"id": case["id"], "question": case["q"], "answer": answer, "tools_called": tools_called,
                     "seconds": round(seconds, 1), "input_tokens": usage.get("inputTokens", 0),
                     "output_tokens": usage.get("outputTokens", 0), **score(case, answer, tools_called)})
        print(f"  {case['id']:<18} {'PASS' if rows[-1]['passed'] else 'FAIL'}  {seconds:6.1f}s  {rows[-1]['missing']}")
    summary = {"model": model, "prompt": prompt, "cases": len(rows),
               "passed": sum(r["passed"] for r in rows),
               "right_tool": sum(r["right_tool"] for r in rows),
               "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2],
               "avg_tokens": round(sum(r["input_tokens"] + r["output_tokens"] for r in rows) / len(rows))}
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{model.replace(':', '-')}_{prompt}.json"
    out.write_text(json.dumps({"summary": summary, "cases": rows}, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--prompt", nargs="+", default=["v1", "v2"])
    args = parser.parse_args()
    summaries = []
    for p in args.prompt:
        print(f"{args.model} / prompt {p}")
        summaries.append(run(args.model, p))
    print("\nmodel        prompt  passed  right tool  median s  avg tokens")
    for s in summaries:
        print(f"{s['model']:<12} {s['prompt']:<7} {s['passed']}/{s['cases']}     {s['right_tool']}/{s['cases']}"
              f"         {s['median_seconds']:<8} {s['avg_tokens']}")
