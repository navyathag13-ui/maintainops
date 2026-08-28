import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ProjectCard } from "../components/ProjectCard";
import { AlertIcon, BoxIcon, TrashIcon } from "../components/icons";
import type { DashboardSummary } from "../types";
import { formatDate, formatDateTime } from "../utils";

function AttentionPanel({
  icon,
  title,
  count,
  emptyLabel,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  emptyLabel: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`attention-panel ${count > 0 ? "attention-panel-warning" : ""}`}>
      <div className="attention-panel-header">
        <span className="attention-panel-icon">{icon}</span>
        <span className="attention-panel-count">{count}</span>
        <span className="attention-panel-title">{title}</span>
      </div>
      {count === 0 ? <p className="subtitle" style={{ margin: 0 }}>{emptyLabel}</p> : <ul className="attention-list">{children}</ul>}
    </div>
  );
}

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.getDashboardSummary().then(setSummary);
  }, []);

  if (!summary) return <p>Loading...</p>;

  const maxLocationCount = Math.max(1, ...summary.equipment_by_location.map((l) => l.count));

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">What needs attention, what's running, and what happened.</p>

      <h2 style={{ marginTop: 0 }}>Requires Attention</h2>
      <div className="attention-grid">
        <AttentionPanel
          icon={<AlertIcon />}
          title="Overdue Equipment"
          count={summary.overdue_equipment.length}
          emptyLabel="Nothing overdue."
        >
          {summary.overdue_equipment.map((eq) => (
            <li key={eq.id}>
              <Link to={`/equipment/${eq.id}`}>
                <span>{eq.name}</span>
                <span className="attention-list-detail">{Number(eq.hours_overdue).toFixed(0)} hrs overdue</span>
              </Link>
            </li>
          ))}
        </AttentionPanel>

        <AttentionPanel
          icon={<BoxIcon />}
          title="Low Stock Parts"
          count={summary.low_stock_parts.length}
          emptyLabel="Nothing low on stock."
        >
          {summary.low_stock_parts.map((part) => (
            <li key={part.id}>
              <Link to="/parts">
                <span>{part.name}</span>
                <span className="attention-list-detail">
                  {part.quantity_on_hand} left, reorder at {part.reorder_threshold}
                </span>
              </Link>
            </li>
          ))}
        </AttentionPanel>

        <AttentionPanel
          icon={<TrashIcon />}
          title="Discard Recommended"
          count={summary.discard_recommended.length}
          emptyLabel="Nothing to discard."
        >
          {summary.discard_recommended.map((eq) => (
            <li key={eq.id}>
              <Link to={`/equipment/${eq.id}`}>
                <span>{eq.name}</span>
                <span className="attention-list-detail">
                  {eq.usage_count} / {eq.max_usage_count} uses
                </span>
              </Link>
            </li>
          ))}
        </AttentionPanel>
      </div>

      <h2>Active Projects</h2>
      {summary.active_projects.length === 0 ? (
        <p className="subtitle">No active projects right now.</p>
      ) : (
        <div className="project-grid">
          {summary.active_projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      <div className="dashboard-two-col">
        <section>
          <h2>Equipment by Location</h2>
          <div className="chart-card location-bars">
            {summary.equipment_by_location.map((loc) => (
              <div className="location-bar-row" key={loc.location}>
                <span className="location-bar-label">{loc.location}</span>
                <div className="location-bar-track">
                  <div
                    className="location-bar-fill"
                    style={{ width: `${(loc.count / maxLocationCount) * 100}%` }}
                  />
                </div>
                <span className="location-bar-count">{loc.count}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2>Due Soon</h2>
          {summary.due_soon.length === 0 ? (
            <p className="subtitle">Nothing due back soon.</p>
          ) : (
            <div className="chart-card due-soon-list">
              {summary.due_soon.map((item) => (
                <Link to={`/equipment/${item.equipment_id}`} className="due-soon-row" key={item.loan_id}>
                  <div>
                    <strong>{item.equipment_name}</strong>
                    <div className="location-bar-label">{item.project_name}</div>
                  </div>
                  <span className={`badge badge-${item.is_overdue_for_return ? "overdue" : "due-soon"}`}>
                    {item.is_overdue_for_return ? "Overdue" : formatDate(item.expected_return_at)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>

      <h2>Recent Activity</h2>
      {summary.recent_activity.length === 0 ? (
        <p className="subtitle">Nothing has happened yet.</p>
      ) : (
        <div className="chart-card activity-feed">
          {summary.recent_activity.map((event) => (
            <div className="activity-row" key={event.id}>
              <span className="activity-row-time">{formatDateTime(event.occurred_at)}</span>
              <span>{event.description}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
