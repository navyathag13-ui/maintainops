import type { ProjectStatus } from "../types";

const LABELS: Record<ProjectStatus, string> = {
  planning: "Planning",
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
};

const LEVEL: Record<ProjectStatus, string> = {
  planning: "due-soon",
  active: "ok",
  on_hold: "overdue",
  completed: "neutral",
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return <span className={`badge badge-${LEVEL[status]}`}>{LABELS[status]}</span>;
}
