import { useEffect, useState } from "react";
import { api } from "../api/client";
import { LowStockBadge } from "../components/LowStockBadge";
import type { Part } from "../types";
import { formatCurrency } from "../utils";

export function PartsPage() {
  const [parts, setParts] = useState<Part[] | null>(null);

  useEffect(() => {
    api.listParts().then(setParts);
  }, []);

  return (
    <div>
      <h1>Parts Inventory</h1>
      {parts === null ? (
        <p>Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>SKU</th>
              <th>Quantity on hand</th>
              <th>Reorder threshold</th>
              <th>Unit cost</th>
              <th>Stock</th>
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
                <td>
                  <LowStockBadge isLowStock={part.is_low_stock} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
