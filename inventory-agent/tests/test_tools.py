"""Tool tests with the API mocked out, so they run without MaintainOps or a model."""

import pytest

from inventory_agent import tools

PARTS = [
    {"name": "Drill Bits", "sku": "DRI-214", "quantity_on_hand": 45, "reorder_threshold": 5},
    {"name": "Oil Filters", "sku": "OIL-170", "quantity_on_hand": 2, "reorder_threshold": 4},
]
LOW = [{"id": 6, "name": "Oil Filters", "sku": "OIL-170", "quantity_on_hand": 2,
        "reorder_threshold": 4, "is_critical": True, "urgency": "urgent"}]
OVERDUE = [{"id": 11, "name": "Angle Grinder #03", "location": "Garage Storage #3",
            "usage_hours": "314.10", "hours_overdue": "14.10"}]


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    routes = {"/parts": PARTS, "/alerts/low-stock": LOW, "/alerts/overdue-maintenance": OVERDUE}
    monkeypatch.setattr(tools, "_get", lambda path: routes[path])


def test_low_stock_keeps_only_what_the_model_needs():
    assert tools.list_low_stock_parts() == [
        {"name": "Oil Filters", "sku": "OIL-170", "quantity_on_hand": 2, "reorder_threshold": 4, "urgency": "urgent"}
    ]


def test_overdue_hours_come_back_as_numbers():
    assert tools.list_overdue_equipment() == [
        {"name": "Angle Grinder #03", "location": "Garage Storage #3", "hours_overdue": 14.1}
    ]


@pytest.mark.parametrize("query", ["drill", "DRILL BITS", " dri-214 "])
def test_find_part_matches_name_or_sku_in_any_case(query):
    assert [p["sku"] for p in tools.find_part(query)] == ["DRI-214"]


def test_unknown_part_returns_empty_list_not_an_error():
    assert tools.find_part("unicorn bolts") == []


def test_every_tool_is_read_only():
    # Writes belong in MaintainOps where a person confirms them; the agent
    # gets no tool that could change stock.
    names = {t.tool_name for t in tools.ALL_TOOLS}
    assert names == {"list_low_stock_parts", "list_overdue_equipment", "find_part"}
    assert not any(word in n for n in names for word in ("set", "update", "delete", "restock", "log"))
