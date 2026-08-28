import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Employee, ProjectStatus, ProjectSummary } from "../types";

export function NewProjectForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: (project: ProjectSummary) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("planning");
  const [managerId, setManagerId] = useState("");
  const [location, setLocation] = useState("");
  const [startDate, setStartDate] = useState("");
  const [expectedEndDate, setExpectedEndDate] = useState("");
  const [managers, setManagers] = useState<Employee[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listEmployees().then((all) => setManagers(all.filter((e) => e.role === "manager")));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const project = await api.createProject({
        name: name.trim(),
        code: code.trim() || null,
        status,
        manager_id: managerId ? Number(managerId) : null,
        location: location.trim() || null,
        start_date: startDate || null,
        expected_end_date: expectedEndDate || null,
      });
      onSuccess(project);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong creating this project.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>New Project</h3>

      <label>
        Name
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. House #8" required />
      </label>

      <label>
        Code (optional)
        <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. HB-008" />
      </label>

      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
          <option value="planning">Planning</option>
          <option value="active">Active</option>
          <option value="on_hold">On Hold</option>
          <option value="completed">Completed</option>
        </select>
      </label>

      <label>
        Manager
        <select value={managerId} onChange={(e) => setManagerId(e.target.value)}>
          <option value="">Unassigned</option>
          {managers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Location
        <input type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. 142 Birch St" />
      </label>

      <label>
        Start date
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
      </label>

      <label>
        Expected end date
        <input type="date" value={expectedEndDate} onChange={(e) => setExpectedEndDate(e.target.value)} />
      </label>

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Creating..." : "Create Project"}
        </button>
      </div>
    </form>
  );
}
