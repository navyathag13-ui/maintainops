import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { Equipment, EquipmentStatus } from "../types";

export function NewEquipmentForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: (equipment: Equipment) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState<EquipmentStatus>("operational");
  const [usageHours, setUsageHours] = useState("0");
  const [intervalHours, setIntervalHours] = useState("");
  const [hasWearLimit, setHasWearLimit] = useState(false);
  const [maxUsageCount, setMaxUsageCount] = useState("5");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const equipment = await api.createEquipment({
        name: name.trim(),
        type: type.trim(),
        location: location.trim(),
        status,
        usage_hours: Number(usageHours),
        maintenance_interval_hours: Number(intervalHours),
        max_usage_count: hasWearLimit ? Number(maxUsageCount) : null,
      });
      onSuccess(equipment);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong adding this equipment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>New Equipment</h3>

      <label>
        Name
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Power Drill 3" required />
      </label>

      <label>
        Type
        <input type="text" value={type} onChange={(e) => setType(e.target.value)} placeholder="e.g. drill, pump, generator" required />
      </label>

      <label>
        Home location
        <input
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g. Garage Back Storage 3"
          required
        />
      </label>

      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value as EquipmentStatus)}>
          <option value="operational">Operational</option>
          <option value="down">Down</option>
          <option value="maintenance">Maintenance</option>
        </select>
      </label>

      <label>
        Starting usage hours
        <input type="number" min={0} step="0.1" value={usageHours} onChange={(e) => setUsageHours(e.target.value)} required />
      </label>

      <label>
        Maintenance interval (hours)
        <input
          type="number"
          min={1}
          step="0.1"
          value={intervalHours}
          onChange={(e) => setIntervalHours(e.target.value)}
          placeholder="e.g. 500"
          required
        />
      </label>

      <label style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
        <input
          type="checkbox"
          checked={hasWearLimit}
          onChange={(e) => setHasWearLimit(e.target.checked)}
          style={{ width: "auto" }}
        />
        This equipment has a limited number of uses before it must be discarded
      </label>

      {hasWearLimit && (
        <label>
          Max uses before discard
          <input
            type="number"
            min={1}
            value={maxUsageCount}
            onChange={(e) => setMaxUsageCount(e.target.value)}
            required
          />
        </label>
      )}

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding..." : "Add Equipment"}
        </button>
      </div>
    </form>
  );
}
