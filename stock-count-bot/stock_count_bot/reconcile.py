"""Compare a physical stock count against what MaintainOps thinks is on hand.

Kept free of Excel and HTTP on purpose: this is the part that decides what
counts as a discrepancy, so it should be testable with plain lists of dicts.
"""

from dataclasses import dataclass, field


@dataclass
class Discrepancy:
    sku: str
    name: str
    status: str  # "short" | "over" | "not_in_system" | "not_counted" | "bad_row"
    system_qty: int | None
    counted_qty: int | None
    note: str = ""

    @property
    def difference(self) -> int | None:
        if self.system_qty is None or self.counted_qty is None:
            return None
        return self.counted_qty - self.system_qty


@dataclass
class ReconcileResult:
    matched: int = 0
    discrepancies: list[Discrepancy] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for d in self.discrepancies if d.status == status)


def _parse_count(raw) -> int | None:
    """Counts come from people typing into a sheet, so accept 12, 12.0 and
    " 12 " but reject anything that isn't a whole, non-negative number."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    if value < 0 or value != int(value):
        return None
    return int(value)


def reconcile(counted_rows: list[dict], system_parts: list[dict]) -> ReconcileResult:
    """counted_rows: rows from the count sheet, each with "sku" and "counted_qty".
    system_parts: parts from GET /parts, each with "sku", "name" and
    "quantity_on_hand"."""
    result = ReconcileResult()
    system_by_sku = {p["sku"].strip().upper(): p for p in system_parts}
    seen: set[str] = set()

    for row in counted_rows:
        sku = str(row.get("sku") or "").strip().upper()
        raw_qty = row.get("counted_qty")
        if not sku:
            result.discrepancies.append(
                Discrepancy("", "", "bad_row", None, None, "row has no SKU")
            )
            continue
        if sku in seen:
            # A part counted twice usually means two people counted the same
            # shelf. Flag it instead of silently keeping either number.
            result.discrepancies.append(
                Discrepancy(sku, "", "bad_row", None, None, "SKU counted more than once")
            )
            continue
        seen.add(sku)

        qty = _parse_count(raw_qty)
        if qty is None:
            result.discrepancies.append(
                Discrepancy(sku, "", "bad_row", None, None, f"count {raw_qty!r} is not a whole number")
            )
            continue

        part = system_by_sku.get(sku)
        if part is None:
            result.discrepancies.append(
                Discrepancy(sku, "", "not_in_system", None, qty, "on the shelf but not in MaintainOps")
            )
            continue

        system_qty = int(part["quantity_on_hand"])
        if qty == system_qty:
            result.matched += 1
        else:
            status = "short" if qty < system_qty else "over"
            result.discrepancies.append(Discrepancy(sku, part["name"], status, system_qty, qty))

    for sku, part in system_by_sku.items():
        if sku not in seen:
            result.discrepancies.append(
                Discrepancy(sku, part["name"], "not_counted", int(part["quantity_on_hand"]), None,
                            "in MaintainOps but missing from the count sheet")
            )

    return result
