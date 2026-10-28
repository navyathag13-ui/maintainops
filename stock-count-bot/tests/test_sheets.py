from robocorp import excel

from stock_count_bot.reconcile import reconcile
from stock_count_bot.sheets import read_count_sheet, write_report

PARTS = [
    {"sku": "BLT-100", "name": "Drive Belt", "quantity_on_hand": 10},
    {"sku": "FLT-200", "name": "Oil Filter", "quantity_on_hand": 4},
]


def test_round_trip_from_count_sheet_to_report(tmp_path):
    sheet = tmp_path / "count.xlsx"
    workbook = excel.create_workbook("xlsx", sheet_name="Count")
    workbook.worksheet("Count").append_rows_to_worksheet(
        [
            {"SKU": "BLT-100", "Counted_Qty": 8, "Counted_By": "J. Rivera"},
            {"SKU": "FLT-200", "Counted_Qty": 4, "Counted_By": "J. Rivera"},
        ],
        header=True,
    )
    workbook.save(sheet)

    counted = read_count_sheet(sheet)
    assert counted == [
        {"sku": "BLT-100", "counted_qty": 8},
        {"sku": "FLT-200", "counted_qty": 4},
    ]

    report = tmp_path / "out" / "report.xlsx"
    write_report(reconcile(counted, PARTS), total_counted=len(counted), path=report)

    saved = excel.open_workbook(report)
    assert saved.list_worksheets() == ["Summary", "Discrepancies"]
    issues = saved.worksheet("Discrepancies").as_table(header=True)
    rows = list(issues)
    assert len(rows) == 1
    assert rows[0]["SKU"] == "BLT-100" and rows[0]["Difference"] == -2
