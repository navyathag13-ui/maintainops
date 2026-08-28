import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Employee, Equipment, EquipmentLoan, ProjectSummary } from "../types";

function defaultReturnDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().slice(0, 10);
}

export function CheckOutForm({
  equipmentId,
  equipmentName,
  projectId,
  projectName,
  managerName,
  onSuccess,
  onCancel,
}: {
  equipmentId?: number;
  equipmentName?: string;
  projectId?: number;
  projectName?: string;
  managerName?: string;
  onSuccess: (loan: EquipmentLoan) => void;
  onCancel: () => void;
}) {
  const [availableEquipment, setAvailableEquipment] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string>(
    equipmentId ? String(equipmentId) : ""
  );
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(
    projectId ? String(projectId) : ""
  );
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [expectedReturn, setExpectedReturn] = useState(defaultReturnDate());
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!equipmentId) {
      api.listEquipment().then((all) => setAvailableEquipment(all.filter((e) => !e.is_checked_out)));
    }
    if (!projectId) {
      api.listProjects().then(setProjects);
    }
    api.listEmployees().then((all) => setEmployees(all.filter((e) => e.active)));
  }, [equipmentId, projectId]);

  const derivedManagerName =
    managerName ?? projects.find((p) => String(p.id) === selectedProjectId)?.manager_name ?? null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const targetEquipmentId = equipmentId ?? Number(selectedEquipmentId);
    const targetProjectId = projectId ?? Number(selectedProjectId);
    const targetEmployeeId = Number(selectedEmployeeId);
    if (!targetEquipmentId) {
      setError("Select which piece of equipment.");
      return;
    }
    if (!targetProjectId) {
      setError("Select which project.");
      return;
    }
    if (!targetEmployeeId) {
      setError("Select who's borrowing it.");
      return;
    }

    setSubmitting(true);
    try {
      const loan = await api.checkOutEquipment(targetEquipmentId, {
        project_id: targetProjectId,
        borrower_employee_id: targetEmployeeId,
        expected_return_at: new Date(expectedReturn).toISOString(),
      });
      onSuccess(loan);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? "This is already checked out to someone else." : err.message);
      } else {
        setError("Something went wrong checking this out.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>
        Check Out{equipmentName ? ` ${equipmentName}` : ""}
        {projectName ? ` for ${projectName}` : ""}
      </h3>

      {!equipmentId && (
        <label>
          What are you borrowing
          <select value={selectedEquipmentId} onChange={(e) => setSelectedEquipmentId(e.target.value)} required>
            <option value="" disabled>
              Select equipment
            </option>
            {availableEquipment.map((eq) => (
              <option key={eq.id} value={eq.id}>
                {eq.name} -- {eq.current_location}
              </option>
            ))}
          </select>
        </label>
      )}

      {!projectId && (
        <label>
          For which project
          <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} required>
            <option value="" disabled>
              Select project
            </option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <label>
        Manager
        <div className="readonly-value">{derivedManagerName ?? "Unassigned"}</div>
      </label>

      <label>
        Borrowed by
        <select value={selectedEmployeeId} onChange={(e) => setSelectedEmployeeId(e.target.value)} required>
          <option value="" disabled>
            Select employee
          </option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Expected return
        <input
          type="date"
          value={expectedReturn}
          onChange={(e) => setExpectedReturn(e.target.value)}
          required
        />
      </label>

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Checking out..." : "Check Out"}
        </button>
      </div>
    </form>
  );
}
