import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { Part, PartRestock } from "../types";

export function RestockForm({
  part,
  onSuccess,
  onCancel,
}: {
  part: Part;
  onSuccess: (restock: PartRestock) => void;
  onCancel: () => void;
}) {
  const [quantity, setQuantity] = useState("1");
  const [unitCost, setUnitCost] = useState(part.unit_cost);
  const [supplier, setSupplier] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const restock = await api.restockPart(part.id, {
        quantity: Number(quantity),
        unit_cost: Number(unitCost),
        supplier: supplier.trim(),
        notes: notes.trim(),
      });
      onSuccess(restock);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong recording this shipment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="log-maintenance-form" onSubmit={handleSubmit}>
      <h3>Restock {part.name}</h3>

      <label>
        Quantity received
        <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
      </label>

      <label>
        Unit cost paid
        <input
          type="number"
          min={0}
          step="0.01"
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
          required
        />
      </label>

      <label>
        Supplier
        <input type="text" value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="e.g. Acme Supply Co" required />
      </label>

      <label>
        Notes (optional)
        <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. bulk order, PO #4521" />
      </label>

      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Record Restock"}
        </button>
      </div>
    </form>
  );
}
