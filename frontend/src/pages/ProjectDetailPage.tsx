import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { CheckOutForm } from "../components/CheckOutForm";
import { EmptyState } from "../components/EmptyState";
import { AlertIcon } from "../components/icons";
import { ProjectStatusBadge } from "../components/ProjectStatusBadge";
import { Toast } from "../components/Toast";
import { UseProjectPartsForm } from "../components/UseProjectPartsForm";
import type { ActivityEvent, Employee, ProjectDetail } from "../types";
import { formatCurrency, formatDate, formatDateTime } from "../utils";

export function ProjectDetailPage() {
  const { id } = useParams();
  const projectId = Number(id);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [assignEmployeeId, setAssignEmployeeId] = useState("");
  const [showAssignEquipment, setShowAssignEquipment] = useState(false);
  const [showUseParts, setShowUseParts] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  function refresh() {
    return Promise.all([
      api.getProject(projectId).then(setProject),
      api.getProjectActivity(projectId).then(setActivity),
    ]);
  }

  useEffect(() => {
    refresh();
    api.listEmployees().then((all) => setEmployees(all.filter((e) => e.active)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  if (!project) return <p>Loading...</p>;

  const teamIds = new Set(project.team.map((t) => t.id));
  const assignableEmployees = employees.filter((e) => !teamIds.has(e.id));

  async function handleAssign(e: React.FormEvent) {
    e.preventDefault();
    if (!assignEmployeeId) return;
    setAssigning(true);
    try {
      await api.assignEmployeeToProject(projectId, Number(assignEmployeeId));
      setAssignEmployeeId("");
      await refresh();
      setToast("Employee assigned to project.");
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : "Couldn't assign that employee.");
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div>
      <Link to="/projects" className="back-link">
        &larr; Back to projects
      </Link>

      <div className="project-detail-header">
        <h1>{project.name}</h1>
        <ProjectStatusBadge status={project.status} />
      </div>
      <p className="subtitle">
        Manager: {project.manager_name ?? "Unassigned"}
        {project.location ? ` · ${project.location}` : ""}
        {project.code ? ` · ${project.code}` : ""}
      </p>

      <div className="stat-grid">
        <div className="mini-stat">
          <div className="mini-stat-value">{project.equipment_count}</div>
          <div className="mini-stat-label">Equipment</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-value">{project.worker_count}</div>
          <div className="mini-stat-label">Workers</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-value">{project.parts_used_count}</div>
          <div className="mini-stat-label">Parts Used</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-value">{project.due_back_soon_count}</div>
          <div className="mini-stat-label">Due Back Soon</div>
        </div>
      </div>

      {project.maintenance_warnings.length > 0 && (
        <div className="maintenance-warning-banner">
          <AlertIcon />
          <div>
            {project.maintenance_warnings.map((w) => (
              <div key={w.equipment_id}>
                <Link to={`/equipment/${w.equipment_id}`}>{w.equipment_name}</Link> -- maintenance overdue by{" "}
                {Number(w.hours_overdue).toFixed(1)} hrs
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", margin: "1.25rem 0" }}>
        {!showAssignEquipment && <button onClick={() => setShowAssignEquipment(true)}>Assign Equipment</button>}
        {!showUseParts && <button onClick={() => setShowUseParts(true)}>Use Parts</button>}
      </div>

      {showAssignEquipment && (
        <CheckOutForm
          projectId={project.id}
          projectName={project.name}
          managerName={project.manager_name ?? undefined}
          onCancel={() => setShowAssignEquipment(false)}
          onSuccess={(loan) => {
            setShowAssignEquipment(false);
            refresh();
            setToast(`${loan.equipment_name} assigned to ${project.name}.`);
          }}
        />
      )}

      {showUseParts && (
        <UseProjectPartsForm
          projectId={project.id}
          projectName={project.name}
          onCancel={() => setShowUseParts(false)}
          onSuccess={() => {
            setShowUseParts(false);
            refresh();
            setToast("Parts usage recorded.");
          }}
        />
      )}

      <h2>Team</h2>
      {project.team.length === 0 ? (
        <EmptyState title="No one assigned yet" description="Assign a team member below." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {project.team.map((member) => (
                <tr key={member.id}>
                  <td>
                    <Link to={`/employees/${member.id}`}>{member.name}</Link>
                  </td>
                  <td>{member.role.replace("_", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {assignableEmployees.length > 0 && (
        <form onSubmit={handleAssign} className="inline-assign-form">
          <select value={assignEmployeeId} onChange={(e) => setAssignEmployeeId(e.target.value)} required>
            <option value="" disabled>
              Add team member...
            </option>
            {assignableEmployees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name} ({emp.role.replace("_", " ")})
              </option>
            ))}
          </select>
          <button type="submit" disabled={assigning}>
            {assigning ? "Adding..." : "Add"}
          </button>
        </form>
      )}

      <h2>Equipment on Site</h2>
      {project.equipment_on_site.length === 0 ? (
        <EmptyState title="Nothing deployed here right now" description="Use Assign Equipment above." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Maintenance</th>
              </tr>
            </thead>
            <tbody>
              {project.equipment_on_site.map((eq) => (
                <tr key={eq.id}>
                  <td>
                    <Link to={`/equipment/${eq.id}`}>{eq.name}</Link>
                  </td>
                  <td>{eq.type}</td>
                  <td>
                    <span className={`badge badge-${eq.is_overdue ? "overdue" : "ok"}`}>
                      {eq.is_overdue ? "Overdue" : "OK"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Parts Used</h2>
      {project.parts_used.length === 0 ? (
        <EmptyState title="No parts consumed yet" description="Use Parts above to record consumption." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Quantity</th>
                <th>Cost</th>
                <th>Employee</th>
                <th>Used at</th>
              </tr>
            </thead>
            <tbody>
              {project.parts_used
                .slice()
                .sort((a, b) => (a.used_at < b.used_at ? 1 : -1))
                .map((usage) => (
                  <tr key={usage.id}>
                    <td>{usage.part_name ?? `#${usage.part_id}`}</td>
                    <td>{usage.quantity}</td>
                    <td>{formatCurrency(Number(usage.unit_cost_at_time) * usage.quantity)}</td>
                    <td>{usage.employee_name ?? "--"}</td>
                    <td>{formatDateTime(usage.used_at)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Activity</h2>
      {activity === null ? (
        <p>Loading...</p>
      ) : activity.length === 0 ? (
        <EmptyState title="Nothing has happened here yet" />
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
              {activity.slice(0, 15).map((event) => (
                <tr key={event.id}>
                  <td>{formatDate(event.occurred_at)}</td>
                  <td>{event.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
