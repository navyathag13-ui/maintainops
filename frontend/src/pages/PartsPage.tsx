import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LowStockBadge } from "../components/LowStockBadge";
import { RestockForm } from "../components/RestockForm";
import { Toast } from "../components/Toast";
import type { Part } from "../types";
import { formatCurrency } from "../utils";

export function PartsPage() {
  const [parts, setParts] = useState<Part[] | null>(null);
  const [restockingPart, setRestockingPart] = useState<Part | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  function refresh() {
    api.listParts().then(setParts);
  }

  useEffect(refresh, []);

  return (
    <div>
      <h1>Parts Inventory</h1>
      <p className="subtitle">Stock on hand, and what needs reordering.</p>
      {parts === null ? (
        <p>Loading...</p>
      ) : parts.length === 0 ? (
        <EmptyState
          title="No parts in inventory yet"
          description="Add parts through the API (or via /docs) before logging maintenance that consumes them."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Quantity on hand</th>
                <th>Reorder threshold</th>
                <th>Unit cost</th>
                <th>Critical</th>
                <th>Stock</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {parts.map((part) => (
                <tr key={part.id}>
                  <td>{part.name}</td>
                  <td>{part.sku}</td>
                  <td>{part.quantity_on_hand}</td>
                  <td>{part.reorder_threshold}</td>
                  <td>{formatCurrency(part.unit_cost)}</td>
                  <td>{part.is_critical ? "Yes" : "--"}</td>
                  <td>
                    <LowStockBadge urgency={part.urgency} />
                  </td>
                  <td>
                    <button type="button" onClick={() => setRestockingPart(part)}>
                      Restock
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {restockingPart && (
        <RestockForm
          key={restockingPart.id}
          part={restockingPart}
          onCancel={() => setRestockingPart(null)}
          onSuccess={(restock) => {
            setRestockingPart(null);
            refresh();
            setToast(`${restock.quantity} x ${restockingPart.name} received from ${restock.supplier}.`);
          }}
        />
      )}

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
