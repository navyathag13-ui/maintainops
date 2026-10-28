# Stock Count Bot (Robocorp)

A Robocorp bot that does the stock-count check a storeroom supervisor would
otherwise do by hand: it reads the spreadsheet a technician filled in while
counting shelves, compares every row against what MaintainOps says is on hand
(`GET /parts`), and writes an Excel report of what needs a second look.

## What it flags

| Issue | What it usually means |
|---|---|
| Short | Parts were taken without being logged against a job |
| Over | A delivery arrived but the restock was never entered |
| On shelf, not in MaintainOps | A new part nobody added to the system |
| Not counted | A shelf nobody got to |
| Bad row | A typo, a count that isn't a whole number, or the same part counted twice |

Duplicates and unreadable counts are flagged rather than guessed at, for the
same reason MaintainOps rejects a short maintenance log instead of applying
half of it: a report people can't trust is worse than no report.

## Results on the sample

`make_sample_count.py` builds a count sheet from the live parts list and
plants 9 known mistakes (3 short, 2 over, 1 unknown part, 1 skipped part,
1 duplicate count, 1 count typed as text), with an answer key in
`data/answer_key.json`. On that sheet the bot checked 42 rows against 40 parts
in under a second and flagged all 9 planted mistakes with no false flags.

## Running it

```bash
# 1. start MaintainOps (from the repo root)
docker compose up -d db backend

# 2. set up the bot
cd stock-count-bot
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 3. build the sample sheet and run the bot
.venv/bin/python make_sample_count.py
.venv/bin/python -m robocorp.tasks run tasks.py

# tests (no API needed)
.venv/bin/python -m pytest -q
```

Settings: `MAINTAINOPS_API` (default `http://localhost:8000`), `COUNT_SHEET`
(default `data/stock_count.xlsx`), `REPORT_PATH`
(default `output/stock_count_report.xlsx`).

## Layout

- `tasks.py`: the Robocorp task; fetches parts and wires the steps together
- `stock_count_bot/reconcile.py`: the comparison rules, kept free of Excel and HTTP so they are easy to test
- `stock_count_bot/sheets.py`: reads the count sheet and writes the report with `robocorp.excel`
- `tests/`: 7 tests covering matches, short and over counts, unknown and uncounted parts, typed counts and a full Excel round trip
