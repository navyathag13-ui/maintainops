import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { LogMaintenanceForm } from "../components/LogMaintenanceForm";
import { MaintenanceStatusBadge } from "../components/MaintenanceStatusBadge";
import type { Equipment, MaintenanceLog } from "../types";
import { formatDateTime, formatHours } from "../utils";

export function EquipmentDetailPage() {
  const { id } = useParams();
  const equipmentId = Number(id);
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [history, setHistory] = useState<MaintenanceLog[] | null>(null);
  const [showForm, setShowForm] = useState(false);

  function refresh() {
    api.getEquipment(equipmentId).then(setEquipment);
    api.getEquipmentHistory(equipmentId).then(setHistory);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [equipmentId]);

  if (!equipment) return <p>Loading...</p>;

  return (
    <div>
      <p>
        <Link to="/equipment">&larr; Back to equipment</Link>
      </p>
      <h1>{equipment.name}</h1>
      <dl className="equipment-detail-grid">
        <dt>Type</dt>
        <dd>{equipment.type}</dd>
        <dt>Location</dt>
        <dd>{equipment.location}</dd>
        <dt>Status</dt>
        <dd>{equipment.status}</dd>
        <dt>Usage hours</dt>
        <dd>{formatHours(equipment.usage_hours)}</dd>
        <dt>Last serviced at</dt>
        <dd>{formatHours(equipment.last_maintenance_usage_hours)}</dd>
        <dt>Maintenance interval</dt>
        <dd>{formatHours(equipment.maintenance_interval_hours)}</dd>
        <dt>Maintenance status</dt>
        <dd>
          <MaintenanceStatusBadge equipment={equipment} />
        </dd>
      </dl>

      {!showForm && <button onClick={() => setShowForm(true)}>Log Maintenance</button>}

      {showForm && (
        <LogMaintenanceForm
          equipmentId={equipment.id}
          onCancel={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            refresh();
          }}
        />
      )}

      <h2>Maintenance history</h2>
      {history === null ? (
        <p>Loading...</p>
      ) : history.length === 0 ? (
        <p>No maintenance logged yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Performed at</th>
              <th>Description</th>
              <th>Parts used</th>
            </tr>
          </thead>
          <tbody>
            {history.map((log) => (
              <tr key={log.id}>
                <td>{formatDateTime(log.performed_at)}</td>
                <td>{log.description}</td>
                <td>
                  {log.parts_used.length === 0
                    ? "--"
                    : log.parts_used
                        .map((pu) => `${pu.part_name ?? `#${pu.part_id}`} x${pu.quantity}`)
                        .join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
