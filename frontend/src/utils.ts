import type { Equipment } from "./types";

export type MaintenanceLevel = "ok" | "due-soon" | "overdue";

// The backend only exposes a boolean is_overdue (the actual business rule).
// "due-soon" is a UI-only warning tier layered on top for the badge, not a
// backend concept -- 80% of the interval elapsed since last service.
const DUE_SOON_THRESHOLD = 0.8;

export function maintenanceLevel(equipment: Equipment): MaintenanceLevel {
  if (equipment.is_overdue) return "overdue";
  const usage = Number(equipment.usage_hours);
  const lastService = Number(equipment.last_maintenance_usage_hours);
  const interval = Number(equipment.maintenance_interval_hours);
  if (interval <= 0) return "ok";
  const fractionElapsed = (usage - lastService) / interval;
  return fractionElapsed >= DUE_SOON_THRESHOLD ? "due-soon" : "ok";
}

export function formatHours(value: string | number): string {
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} hrs`;
}

export function formatCurrency(value: string | number): string {
  return Number(value).toLocaleString(undefined, { style: "currency", currency: "USD" });
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString();
}
