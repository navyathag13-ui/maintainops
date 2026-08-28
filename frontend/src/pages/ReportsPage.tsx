import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { StatCard } from "../components/StatCard";
import { BoxIcon, WrenchIcon } from "../components/icons";
import type { MaintenanceCostReport, PartsSpendReport } from "../types";
import { formatCurrency } from "../utils";

const ACCENT = "#b45309";
const MUTED = "#77705f";

export function ReportsPage() {
  const [maintenanceCost, setMaintenanceCost] = useState<MaintenanceCostReport | null>(null);
  const [partsSpend, setPartsSpend] = useState<PartsSpendReport | null>(null);

  useEffect(() => {
    api.getMaintenanceCostReport().then(setMaintenanceCost);
    api.getPartsSpendReport().then(setPartsSpend);
  }, []);

  const equipmentChartData =
    maintenanceCost?.by_equipment.map((e) => ({
      name: e.equipment_name,
      cost: Number(e.total_cost),
    })) ?? [];

  const spendByMonthData =
    partsSpend?.by_month.map((m) => ({
      month: m.month,
      spend: Number(m.total_cost),
    })) ?? [];

  return (
    <div>
      <h1>Reports</h1>
      <p className="subtitle">What keeping the fleet running has actually cost.</p>

      <div className="stat-grid">
        <StatCard
          label="Maintenance cost (parts consumed)"
          value={maintenanceCost ? formatCurrency(maintenanceCost.total_cost) : "..."}
          icon={<WrenchIcon />}
        />
        <StatCard
          label="Parts spend (inventory purchased)"
          value={partsSpend ? formatCurrency(partsSpend.total_cost) : "..."}
          icon={<BoxIcon />}
        />
      </div>

      <h2>Maintenance cost by equipment</h2>
      {equipmentChartData.length === 0 ? (
        <p className="subtitle">No maintenance logged with parts yet.</p>
      ) : (
        <div className="chart-card">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={equipmentChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6e0d4" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: MUTED }} />
              <YAxis tick={{ fontSize: 12, fill: MUTED }} tickFormatter={(v) => `$${v}`} />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Bar dataKey="cost" fill={ACCENT} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {maintenanceCost && maintenanceCost.by_equipment.length > 0 && (
        <div className="table-scroll" style={{ marginTop: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>Equipment</th>
                <th>Total cost</th>
                <th>Maintenance events</th>
              </tr>
            </thead>
            <tbody>
              {maintenanceCost.by_equipment.map((e) => (
                <tr key={e.equipment_id}>
                  <td>{e.equipment_name}</td>
                  <td>{formatCurrency(e.total_cost)}</td>
                  <td>{e.maintenance_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Parts spend by month</h2>
      {spendByMonthData.length === 0 ? (
        <p className="subtitle">No restocks logged yet.</p>
      ) : (
        <div className="chart-card">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={spendByMonthData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6e0d4" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: MUTED }} />
              <YAxis tick={{ fontSize: 12, fill: MUTED }} tickFormatter={(v) => `$${v}`} />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Line type="monotone" dataKey="spend" stroke={ACCENT} strokeWidth={2.5} dot={{ fill: ACCENT }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {partsSpend && partsSpend.by_part.length > 0 && (
        <div className="table-scroll" style={{ marginTop: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>Part</th>
                <th>Total spend</th>
                <th>Quantity received</th>
              </tr>
            </thead>
            <tbody>
              {partsSpend.by_part.map((p) => (
                <tr key={p.part_id}>
                  <td>{p.part_name}</td>
                  <td>{formatCurrency(p.total_cost)}</td>
                  <td>{p.total_quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
