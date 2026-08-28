import type { PartUrgency } from "../types";

const LABELS: Record<PartUrgency, string> = {
  none: "In stock",
  watch: "Watch",
  urgent: "Urgent",
};

const LEVEL: Record<PartUrgency, string> = {
  none: "ok",
  watch: "due-soon",
  urgent: "overdue",
};

export function LowStockBadge({ urgency }: { urgency: PartUrgency }) {
  return <span className={`badge badge-${LEVEL[urgency]}`}>{LABELS[urgency]}</span>;
}
