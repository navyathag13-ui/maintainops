"""Excel in, Excel out, using Robocorp's excel library."""

from pathlib import Path

from robocorp import excel

from .reconcile import ReconcileResult

STATUS_LABELS = {
    "short": "Short (fewer on shelf than recorded)",
    "over": "Over (more on shelf than recorded)",
    "not_in_system": "On shelf, not in MaintainOps",
    "not_counted": "Not counted",
    "bad_row": "Bad row in count sheet",
}


def read_count_sheet(path: Path) -> list[dict]:
    """Expects a header row with at least "sku" and "counted_qty" columns
    (case-insensitive); any other columns, like who counted, are ignored."""
    workbook = excel.open_workbook(path)
    table = workbook.worksheet(0).as_table(header=True)
    rows = []
    for row in table:
        normalized = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
        if not any(v not in (None, "") for v in normalized.values()):
            continue  # fully blank line at the bottom of the sheet
        rows.append({"sku": normalized.get("sku"), "counted_qty": normalized.get("counted_qty")})
    return rows


def write_report(result: ReconcileResult, total_counted: int, path: Path) -> None:
    summary = [
        ["Metric", "Value"],
        ["Rows in count sheet", total_counted],
        ["Parts that matched", result.matched],
        ["Short", result.count("short")],
        ["Over", result.count("over")],
        ["On shelf, not in MaintainOps", result.count("not_in_system")],
        ["Not counted", result.count("not_counted")],
        ["Bad rows", result.count("bad_row")],
    ]
    workbook = excel.create_workbook("xlsx", sheet_name="Summary")
    workbook.worksheet("Summary").append_rows_to_worksheet(summary)

    rows = [["SKU", "Part", "Issue", "In MaintainOps", "Counted", "Difference", "Note"]]
    for d in result.discrepancies:
        rows.append([d.sku, d.name, STATUS_LABELS[d.status], d.system_qty, d.counted_qty,
                     d.difference, d.note])
    workbook.create_worksheet("Discrepancies", content=rows)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
