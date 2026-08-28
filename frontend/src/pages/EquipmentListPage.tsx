import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { MaintenanceStatusBadge } from "../components/MaintenanceStatusBadge";
import type { Equipment } from "../types";
import { formatHours } from "../utils";

export function EquipmentListPage() {
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);

  useEffect(() => {
    api.listEquipment().then(setEquipment);
  }, []);

  return (
    <div>
      <h1>Equipment</h1>
      <p className="subtitle">The full fleet, and where each piece stands on maintenance.</p>
      {equipment === null ? (
        <p>Loading...</p>
      ) : equipment.length === 0 ? (
        <EmptyState
          title="No equipment yet"
          description="Add equipment through the API (or via /docs) to start tracking maintenance."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Location</th>
                <th>Status</th>
                <th>Usage hours</th>
                <th>Maintenance</th>
              </tr>
            </thead>
            <tbody>
              {equipment.map((eq) => (
                <tr key={eq.id}>
                  <td>
                    <Link to={`/equipment/${eq.id}`}>{eq.name}</Link>
                  </td>
                  <td>{eq.location}</td>
                  <td>{eq.status}</td>
                  <td>{formatHours(eq.usage_hours)}</td>
                  <td>
                    <MaintenanceStatusBadge equipment={eq} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
