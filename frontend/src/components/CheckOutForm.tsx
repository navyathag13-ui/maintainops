import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Equipment, EquipmentLoan } from "../types";

function defaultReturnDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().slice(0, 10);
}

export function CheckOutForm({
  equipmentId,
  equipmentName,
  onSuccess,
  onCancel,
}: {
  equipmentId?: number;
  equipmentName?: string;
  onSuccess: (loan: EquipmentLoan) => void;
  onCancel: () => void;
}) {
  const [availableEquipment, setAvailableEquipment] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string>(
    equipmentId ? String(equipmentId) : ""
  );
  const [project, setProject] = useState("");
  const [managerName, setManagerName] = useState("");
  const [borrowerName, setBorrowerName] = useState("");
  const [expectedReturn, setExpectedReturn] = useState(defaultReturnDate());
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!equipmentId) {
      api.listEquipment().then((all) => setAvailableEquipment(all.filter((e) => !e.is_checked_out)));
    }
  }, [equipmentId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const targetId = equipmentId ?? Number(selectedEquipmentId);
    if (!targetId) {
      setError("Select which piece of equipment.");
      return;
    }

    setSubmitting(true);
    try {
      const loan = await api.checkOutEquipment(targetId, {
        project: project.trim(),
        manager_name: managerName.trim(),
        borrower_name: borrowerName.trim(),
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
      <h3>Check Out{equipmentName ? ` ${equipmentName}` : ""}</h3>

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

      <label>
        For which project
        <input
          type="text"
          value={project}
          onChange={(e) => setProject(e.target.value)}
          placeholder="e.g. House Build #123"
          required
        />
      </label>

      <label>
        Manager
        <input
          type="text"
          value={managerName}
          onChange={(e) => setManagerName(e.target.value)}
          placeholder="Who's signing off on this"
          required
        />
      </label>

      <label>
        Borrower
        <input
          type="text"
          value={borrowerName}
          onChange={(e) => setBorrowerName(e.target.value)}
          placeholder="Who's taking it"
          required
        />
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
