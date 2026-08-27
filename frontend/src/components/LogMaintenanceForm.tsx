import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Equipment, MaintenanceLog, Part } from "../types";

interface PartRow {
  partId: string;
  quantity: string;
}

export function LogMaintenanceForm({
  equipmentId,
  onSuccess,
  onCancel,
}: {
  equipmentId?: number;
  onSuccess: (log: MaintenanceLog) => void;
  onCancel: () => void;
}) {
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [parts, setParts] = useState<Part[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string>(
    equipmentId ? String(equipmentId) : ""
  );
  const [description, setDescription] = useState("");
  const [partRows, setPartRows] = useState<PartRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listParts().then(setParts).catch(() => setError("Failed to load parts."));
    if (!equipmentId) {
      api.listEquipment().then(setEquipmentList).catch(() => setError("Failed to load equipment."));
    }
  }, [equipmentId]);

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

    const targetEquipmentId = equipmentId ?? Number(selectedEquipmentId);
    if (!targetEquipmentId) {
      setError("Select equipment.");
      return;
    }
    if (!description.trim()) {
      setError("Description is required.");
      return;
    }

    const usedParts = partRows
      .filter((row) => row.partId)
      .map((row) => ({ part_id: Number(row.partId), quantity: Number(row.quantity) }));

    setSubmitting(true);
    try {
      const log = await api.createMaintenanceLog({
        equipment_id: targetEquipmentId,
        description: description.trim(),
        parts_used: usedParts,
      });
      onSuccess(log);
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
        setError("Something went wrong submitting this log.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>Log Maintenance</h3>

      {!equipmentId && (
        <label>
          Equipment
          <select
            value={selectedEquipmentId}
            onChange={(e) => setSelectedEquipmentId(e.target.value)}
            required
          >
            <option value="" disabled>
              Select equipment
            </option>
            {equipmentList.map((eq) => (
              <option key={eq.id} value={eq.id}>
                {eq.name} -- {eq.location}
              </option>
            ))}
          </select>
        </label>
      )}

      <label>
        Description
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          required
        />
      </label>

      <div className="parts-used-section">
        <div className="parts-used-header">
          <span>Parts used</span>
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
            <button type="button" onClick={() => removePartRow(index)} aria-label="Remove part">
              &times;
            </button>
          </div>
        ))}
      </div>

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Save"}
        </button>
      </div>
    </form>
  );
}
