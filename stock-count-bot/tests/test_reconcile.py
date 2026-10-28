from stock_count_bot.reconcile import reconcile

PARTS = [
    {"sku": "BLT-100", "name": "Drive Belt", "quantity_on_hand": 10},
    {"sku": "FLT-200", "name": "Oil Filter", "quantity_on_hand": 4},
    {"sku": "GRS-300", "name": "Grease", "quantity_on_hand": 0},
]


def statuses(result):
    return {(d.sku, d.status) for d in result.discrepancies}


def test_exact_count_matches():
    counted = [{"sku": p["sku"], "counted_qty": p["quantity_on_hand"]} for p in PARTS]
    result = reconcile(counted, PARTS)
    assert result.matched == 3
    assert result.discrepancies == []


def test_short_and_over_carry_the_difference():
    counted = [
        {"sku": "BLT-100", "counted_qty": 7},
        {"sku": "FLT-200", "counted_qty": 9},
        {"sku": "GRS-300", "counted_qty": 0},
    ]
    result = reconcile(counted, PARTS)
    by_sku = {d.sku: d for d in result.discrepancies}
    assert by_sku["BLT-100"].status == "short" and by_sku["BLT-100"].difference == -3
    assert by_sku["FLT-200"].status == "over" and by_sku["FLT-200"].difference == 5
    assert result.matched == 1


def test_unknown_and_uncounted_parts_are_both_reported():
    counted = [
        {"sku": "BLT-100", "counted_qty": 10},
        {"sku": "FLT-200", "counted_qty": 4},
        {"sku": "XYZ-999", "counted_qty": 2},
    ]
    result = reconcile(counted, PARTS)
    assert statuses(result) == {("XYZ-999", "not_in_system"), ("GRS-300", "not_counted")}


def test_sku_matching_ignores_case_and_spaces():
    counted = [{"sku": " blt-100 ", "counted_qty": "10"}]
    result = reconcile(counted, PARTS[:1])
    assert result.matched == 1


def test_people_typing_counts_are_handled():
    counted = [
        {"sku": "BLT-100", "counted_qty": 10.0},     # Excel number, fine
        {"sku": "FLT-200", "counted_qty": "four"},   # text, rejected
        {"sku": "GRS-300", "counted_qty": -1},        # negative, rejected
        {"sku": "", "counted_qty": 3},                # missing SKU
    ]
    result = reconcile(counted, PARTS)
    assert result.matched == 1
    assert result.count("bad_row") == 3


def test_duplicate_count_is_flagged_not_silently_kept():
    counted = [
        {"sku": "BLT-100", "counted_qty": 10},
        {"sku": "BLT-100", "counted_qty": 8},
        {"sku": "FLT-200", "counted_qty": 4},
        {"sku": "GRS-300", "counted_qty": 0},
    ]
    result = reconcile(counted, PARTS)
    assert result.matched == 3
    assert statuses(result) == {("BLT-100", "bad_row")}
