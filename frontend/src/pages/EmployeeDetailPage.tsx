import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ProjectStatusBadge } from "../components/ProjectStatusBadge";
import type { EmployeeDetail } from "../types";
import { formatDate, formatDateTime } from "../utils";

const ROLE_LABELS: Record<string, string> = {
  manager: "Manager",
  technician: "Technician",
  equipment_operator: "Equipment Operator",
  site_worker: "Site Worker",
};

export function EmployeeDetailPage() {
  const { id } = useParams();
  const employeeId = Number(id);
  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);

  useEffect(() => {
    api.getEmployee(employeeId).then(setEmployee);
  }, [employeeId]);

  if (!employee) return <p>Loading...</p>;

  return (
    <div>
      <Link to="/employees" className="back-link">
        &larr; Back to employees
      </Link>
      <h1>{employee.name}</h1>
      <dl className="equipment-detail-grid">
        <dt>Role</dt>
        <dd>{ROLE_LABELS[employee.role] ?? employee.role}</dd>
        <dt>Status</dt>
        <dd>
          <span className={`badge badge-${employee.active ? "ok" : "neutral"}`}>
            {employee.active ? "Active" : "Inactive"}
          </span>
        </dd>
      </dl>

      <h2>Current Projects</h2>
      {employee.current_projects.length === 0 ? (
        <EmptyState title="Not assigned to a project right now" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Project</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {employee.current_projects.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/projects/${p.id}`}>{p.name}</Link>
                  </td>
                  <td>
                    <ProjectStatusBadge status={p.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Equipment Currently Borrowed</h2>
      {employee.borrowed_equipment.length === 0 ? (
        <EmptyState title="Not holding any equipment right now" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Equipment</th>
                <th>Project</th>
                <th>Expected return</th>
              </tr>
            </thead>
            <tbody>
              {employee.borrowed_equipment.map((eq) => (
                <tr key={eq.id}>
                  <td>
                    <Link to={`/equipment/${eq.id}`}>{eq.name}</Link>
                  </td>
                  <td>{eq.project_name ?? "--"}</td>
                  <td>{formatDate(eq.expected_return_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Recent Activity</h2>
      {employee.recent_activity.length === 0 ? (
        <EmptyState title="No activity yet" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>What happened</th>
              </tr>
            </thead>
            <tbody>
              {employee.recent_activity.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.occurred_at)}</td>
                  <td>{event.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
