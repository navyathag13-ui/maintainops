"""Read-only tools over the MaintainOps REST API.

Every tool only reads. A supervisor can ask the agent anything without the
risk of it changing stock: writes stay with the app and the voice agent,
where a person confirms them first.

The descriptions matter as much as the code: they are what the model reads
when it decides which tool to call, so each one says what it returns and
when to use it.
"""

import os

import requests
from strands import tool

API_URL = os.getenv("MAINTAINOPS_API", "http://localhost:8000")


def _get(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


@tool
def list_low_stock_parts() -> list[dict]:
    """List parts at or below their reorder threshold. Use for questions like
    "what are we running low on" or "what should I reorder". Returns name, SKU,
    quantity on hand, reorder threshold and urgency ("watch" or "urgent")."""
    return [
        {k: p[k] for k in ("name", "sku", "quantity_on_hand", "reorder_threshold", "urgency")}
        for p in _get("/alerts/low-stock")
    ]


@tool
def list_overdue_equipment() -> list[dict]:
    """List equipment past its maintenance interval, based on usage hours.
    Use for "what is overdue" or "what needs maintenance". Returns name,
    location and how many usage hours past due it is."""
    return [
        {"name": e["name"], "location": e["location"], "hours_overdue": float(e["hours_overdue"])}
        for e in _get("/alerts/overdue-maintenance")
    ]


@tool
def find_part(query: str) -> list[dict]:
    """Look up parts by SKU or by words in the part name (case-insensitive),
    for questions like "how many oil filters do we have". Returns every match
    with name, SKU and quantity on hand; an empty list means no such part."""
    q = query.strip().lower()
    return [
        {"name": p["name"], "sku": p["sku"], "quantity_on_hand": p["quantity_on_hand"]}
        for p in _get("/parts")
        if q in p["sku"].lower() or q in p["name"].lower()
    ]


ALL_TOOLS = [list_low_stock_parts, list_overdue_equipment, find_part]
