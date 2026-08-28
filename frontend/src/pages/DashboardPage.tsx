import { useEffect, useState } from "react";
import { api } from "../api/client";
import { AlertIcon, BoxIcon } from "../components/icons";
import { StatCard } from "../components/StatCard";
import type { LowStockPart, OverdueEquipment } from "../types";

export function DashboardPage() {
  const [overdue, setOverdue] = useState<OverdueEquipment[] | null>(null);
  const [lowStock, setLowStock] = useState<LowStockPart[] | null>(null);

  useEffect(() => {
    api.getOverdueMaintenance().then(setOverdue);
    api.getLowStock().then(setLowStock);
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">What needs attention right now.</p>
      <div className="stat-grid">
        <StatCard
          label="Overdue equipment"
          value={overdue ? overdue.length : "..."}
          tone={overdue && overdue.length > 0 ? "warning" : "neutral"}
          icon={<AlertIcon />}
        />
        <StatCard
          label="Low-stock parts"
          value={lowStock ? lowStock.length : "..."}
          tone={lowStock && lowStock.length > 0 ? "warning" : "neutral"}
          icon={<BoxIcon />}
        />
      </div>

      {overdue && overdue.length > 0 && (
        <section>
          <h2>Overdue equipment</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Hours overdue</th>
                </tr>
              </thead>
              <tbody>
                {overdue.map((eq) => (
                  <tr key={eq.id}>
                    <td>{eq.name}</td>
                    <td>{eq.location}</td>
                    <td>{Number(eq.hours_overdue).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {lowStock && lowStock.length > 0 && (
        <section>
          <h2>Low-stock parts</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>SKU</th>
                  <th>On hand</th>
                  <th>Reorder threshold</th>
                </tr>
              </thead>
              <tbody>
                {lowStock.map((part) => (
                  <tr key={part.id}>
                    <td>{part.name}</td>
                    <td>{part.sku}</td>
                    <td>{part.quantity_on_hand}</td>
                    <td>{part.reorder_threshold}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {overdue && lowStock && overdue.length === 0 && lowStock.length === 0 && (
        <p className="subtitle" style={{ marginTop: "1.5rem" }}>
          Nothing overdue and nothing low on stock. Nice work.
        </p>
      )}
    </div>
  );
}
