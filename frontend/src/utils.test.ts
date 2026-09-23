import { describe, expect, it } from "vitest";
import type { Equipment } from "./types";
import { formatCurrency, maintenanceLevel } from "./utils";

function equipment(overrides: Partial<Equipment>): Equipment {
  return {
    id: 1,
    name: "Pump",
    type: "pump",
    location: "Bay 1",
    current_location: "Bay 1",
    status: "operational",
    usage_hours: "0",
    last_maintenance_usage_hours: "0",
    maintenance_interval_hours: "100",
    is_overdue: false,
    usage_count: 0,
    max_usage_count: null,
    is_at_wear_limit: false,
    is_checked_out: false,
    ...overrides,
  };
}

describe("maintenanceLevel", () => {
  it("is ok early in the interval", () => {
    expect(maintenanceLevel(equipment({ usage_hours: "10" }))).toBe("ok");
  });

  it("switches to due-soon at exactly 80% of the interval", () => {
    expect(maintenanceLevel(equipment({ usage_hours: "79.9" }))).toBe("ok");
    expect(maintenanceLevel(equipment({ usage_hours: "80" }))).toBe("due-soon");
  });

  it("measures from the last service, not from zero", () => {
    expect(maintenanceLevel(equipment({ usage_hours: "1050", last_maintenance_usage_hours: "1000" }))).toBe("ok");
    expect(maintenanceLevel(equipment({ usage_hours: "1085", last_maintenance_usage_hours: "1000" }))).toBe("due-soon");
  });

  it("trusts the backend's overdue flag", () => {
    expect(maintenanceLevel(equipment({ is_overdue: true }))).toBe("overdue");
  });

  it("does not divide by a zero interval", () => {
    expect(maintenanceLevel(equipment({ maintenance_interval_hours: "0", usage_hours: "50" }))).toBe("ok");
  });
});

describe("formatCurrency", () => {
  it("formats dollars", () => {
    expect(formatCurrency("12.5")).toContain("12.50");
  });
});
