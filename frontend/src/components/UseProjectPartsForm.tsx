import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Employee, Part, ProjectPartUsage } from "../types";

interface PartRow {
  partId: string;
  quantity: string;
}

export function UseProjectPartsForm({
  projectId,
  projectName,
  onSuccess,
  onCancel,
}: {
  projectId: number;
  projectName: string;
  onSuccess: (usages: ProjectPartUsage[]) => void;
  onCancel: () => void;
}) {
  const [parts, setParts] = useState<Part[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [partRows, setPartRows] = useState<PartRow[]>([{ partId: "", quantity: "1" }]);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listParts().then(setParts);
    api.listEmployees().then((all) => setEmployees(all.filter((e) => e.active)));
  }, []);

  function addPartRow() {
    setPartRows([...partRows, { partId: "", quantity: "1" }]);
  }

  function updatePartRow(index: number, field: keyof PartRow, value: string) {
    setPartRows(partRows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function removePartRow(index: number) {
    setPartRows(partRows.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const usedParts = partRows
      .filter((row) => row.partId)
      .map((row) => ({ part_id: Number(row.partId), quantity: Number(row.quantity) }));
    if (usedParts.length === 0) {
      setError("Add at least one part.");
      return;
    }

    setSubmitting(true);
    try {
      const usages = await api.useProjectParts(projectId, {
        parts_used: usedParts,
        employee_id: employeeId ? Number(employeeId) : null,
        note: note.trim(),
      });
      onSuccess(usages);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.shortfalls?.length) {
          const detail = err.shortfalls
            .map((s) => `part ${s.part_id}: requested ${s.requested}, only ${s.available} available`)
            .join("; ");
          setError(`Not enough stock -- ${detail}`);
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong recording this.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>Use Parts on {projectName}</h3>

      <label>
        Employee (optional)
        <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
          <option value="">Not specified</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.name}
            </option>
          ))}
        </select>
      </label>

      <div className="parts-used-section">
        <div className="parts-used-header">
          <span>Parts</span>
          <button type="button" onClick={addPartRow}>
            + Add part
          </button>
        </div>
        {partRows.map((row, index) => (
          <div className="part-row" key={index}>
            <select
              value={row.partId}
              onChange={(e) => updatePartRow(index, "partId", e.target.value)}
              required
            >
              <option value="" disabled>
                Select part
              </option>
              {parts.map((part) => (
                <option key={part.id} value={part.id}>
                  {part.name} ({part.quantity_on_hand} in stock)
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              value={row.quantity}
              onChange={(e) => updatePartRow(index, "quantity", e.target.value)}
              required
            />
            {partRows.length > 1 && (
              <button type="button" onClick={() => removePartRow(index)} aria-label="Remove part">
                &times;
              </button>
            )}
          </div>
        ))}
      </div>

      <label>
        Note (optional)
        <input type="text" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. framing, 2nd floor" />
      </label>

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Use Parts"}
        </button>
      </div>
    </form>
  );
}
