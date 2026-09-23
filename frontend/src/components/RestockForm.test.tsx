import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Part } from "../types";
import { RestockForm } from "./RestockForm";

function part(id: number, unitCost: string): Part {
  return {
    id,
    name: `Part ${id}`,
    sku: `SKU-${id}`,
    quantity_on_hand: 5,
    reorder_threshold: 2,
    unit_cost: unitCost,
    is_critical: false,
    is_low_stock: false,
    urgency: "none",
  };
}

describe("RestockForm", () => {
  it("starts with the part's current unit cost", () => {
    render(<RestockForm part={part(1, "12.50")} onSuccess={() => {}} onCancel={() => {}} />);
    expect(screen.getByDisplayValue("12.50")).toBeInTheDocument();
  });

  it("shows the new part's price when it is remounted with a different key", () => {
    // Regression: without a key on the parent, switching to another part kept the
    // previous part's price in the field. The fix is `key={part.id}` at the call site.
    const { rerender } = render(<RestockForm key={1} part={part(1, "12.50")} onSuccess={() => {}} onCancel={() => {}} />);
    rerender(<RestockForm key={2} part={part(2, "99.00")} onSuccess={() => {}} onCancel={() => {}} />);
    expect(screen.getByDisplayValue("99.00")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("12.50")).not.toBeInTheDocument();
  });
});
