"""Robocorp task: reconcile a physical stock count against MaintainOps.

Run with:  python -m robocorp.tasks run tasks.py
Settings come from environment variables so the same bot can point at a
local or a deployed MaintainOps.
"""

import os
import time
from pathlib import Path

import requests
from robocorp.tasks import task

from stock_count_bot.reconcile import reconcile
from stock_count_bot.sheets import read_count_sheet, write_report

API_URL = os.getenv("MAINTAINOPS_API", "http://localhost:8000")
COUNT_SHEET = Path(os.getenv("COUNT_SHEET", "data/stock_count.xlsx"))
REPORT_PATH = Path(os.getenv("REPORT_PATH", "output/stock_count_report.xlsx"))


def fetch_parts(api_url: str) -> list[dict]:
    response = requests.get(f"{api_url}/parts", timeout=10)
    # Fail loudly: a report built from a half-loaded parts list would flag
    # every missing part as "not counted" and send someone to recount shelves.
    response.raise_for_status()
    return response.json()


@task
def reconcile_stock_count():
    started = time.perf_counter()
    counted = read_count_sheet(COUNT_SHEET)
    parts = fetch_parts(API_URL)
    result = reconcile(counted, parts)
    write_report(result, total_counted=len(counted), path=REPORT_PATH)
    elapsed = time.perf_counter() - started
    print(
        f"Checked {len(counted)} counted rows against {len(parts)} parts in {elapsed:.2f} s: "
        f"{result.matched} matched, {len(result.discrepancies)} need review. Report: {REPORT_PATH}"
    )
