"""Build a realistic count sheet from the live parts list, with known mistakes
planted in it, plus an answer key. This is how the bot is checked end to end:
run it on this sheet and every planted mistake should show up in the report.

Usage:  python make_sample_count.py   (MaintainOps API must be running)
"""

import json
import random
from pathlib import Path

from robocorp import excel

from tasks import API_URL, COUNT_SHEET, fetch_parts

SEED = 7


def main():
    rng = random.Random(SEED)
    parts = fetch_parts(API_URL)
    rows = [{"sku": p["sku"], "counted_qty": p["quantity_on_hand"], "counted_by": "J. Rivera"} for p in parts]
    picks = rng.sample(range(len(rows)), 6)
    key = []

    for i in picks[:3]:  # someone took parts without logging them
        rows[i]["counted_qty"] = max(0, rows[i]["counted_qty"] - rng.randint(1, 4))
        key.append({"sku": rows[i]["sku"], "status": "short"})
    for i in picks[3:5]:  # a restock arrived but was never entered
        rows[i]["counted_qty"] += rng.randint(2, 10)
        key.append({"sku": rows[i]["sku"], "status": "over"})
    missed = rows.pop(picks[5])  # a shelf nobody got to
    key.append({"sku": missed["sku"], "status": "not_counted"})

    rows.append({"sku": "GLV-999", "counted_qty": 12, "counted_by": "J. Rivera"})
    key.append({"sku": "GLV-999", "status": "not_in_system"})
    rows.append({"sku": rows[0]["sku"], "counted_qty": rows[0]["counted_qty"], "counted_by": "A. Chen"})
    key.append({"sku": rows[0]["sku"], "status": "bad_row"})
    rows.append({"sku": rows[1]["sku"].lower(), "counted_qty": "twelve", "counted_by": "A. Chen"})
    # rows[1] is now counted twice (once lowercase), so it is also a duplicate
    key.append({"sku": rows[1]["sku"], "status": "bad_row"})

    COUNT_SHEET.parent.mkdir(parents=True, exist_ok=True)
    workbook = excel.create_workbook("xlsx", sheet_name="Count")
    workbook.worksheet("Count").append_rows_to_worksheet(rows, header=True)
    workbook.save(COUNT_SHEET)
    COUNT_SHEET.with_name("answer_key.json").write_text(json.dumps(key, indent=2))
    print(f"Wrote {len(rows)} rows to {COUNT_SHEET} with {len(key)} planted mistakes")


if __name__ == "__main__":
    main()
