import type { Equipment } from "../types";
import { maintenanceLevel } from "../utils";

const LABELS: Record<string, string> = {
  ok: "OK",
  "due-soon": "Due soon",
  overdue: "Overdue",
};

export function MaintenanceStatusBadge({ equipment }: { equipment: Equipment }) {
  const level = maintenanceLevel(equipment);
  return <span className={`badge badge-${level}`}>{LABELS[level]}</span>;
}
