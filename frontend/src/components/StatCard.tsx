import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: number | string;
  tone?: "neutral" | "warning";
  icon?: ReactNode;
}) {
  return (
    <div className={`stat-card stat-card-${tone}`}>
      {icon && <span className="stat-card-icon">{icon}</span>}
      <div>
        <div className="stat-card-value">{value}</div>
        <div className="stat-card-label">{label}</div>
      </div>
    </div>
  );
}
