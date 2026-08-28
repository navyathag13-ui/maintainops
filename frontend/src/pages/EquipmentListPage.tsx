import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { MapPinIcon } from "../components/icons";
import { MaintenanceStatusBadge } from "../components/MaintenanceStatusBadge";
import { NewEquipmentForm } from "../components/NewEquipmentForm";
import { Toast } from "../components/Toast";
import { WearLimitBadge } from "../components/WearLimitBadge";
import type { Equipment } from "../types";
import { formatHours } from "../utils";

export function EquipmentListPage() {
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function refresh() {
    api.listEquipment().then(setEquipment);
  }

  useEffect(refresh, []);

  return (
    <div>
      <h1>Equipment</h1>
      <p className="subtitle">The full fleet, and where each piece stands on maintenance.</p>

      {!showForm && <button onClick={() => setShowForm(true)}>+ New Equipment</button>}

      {showForm && (
        <NewEquipmentForm
          onCancel={() => setShowForm(false)}
          onSuccess={(eq) => {
            setShowForm(false);
            refresh();
            setToast(`${eq.name} added to the fleet.`);
          }}
        />
      )}

      <div style={{ marginTop: "1.25rem" }}>
        {equipment === null ? (
          <p>Loading...</p>
        ) : equipment.length === 0 ? (
          <EmptyState title="No equipment yet" description="Add the first piece of equipment above." />
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
                  <th>Wear</th>
                </tr>
              </thead>
              <tbody>
                {equipment.map((eq) => (
                  <tr key={eq.id}>
                    <td>
                      <Link to={`/equipment/${eq.id}`}>{eq.name}</Link>
                    </td>
                    <td>
                      {eq.is_checked_out ? (
                        <span className="location-away">
                          <MapPinIcon /> {eq.current_location}
                        </span>
                      ) : (
                        eq.current_location
                      )}
                    </td>
                    <td>{eq.status}</td>
                    <td>{formatHours(eq.usage_hours)}</td>
                    <td>
                      <MaintenanceStatusBadge equipment={eq} />
                    </td>
                    <td>
                      <WearLimitBadge usageCount={eq.usage_count} maxUsageCount={eq.max_usage_count} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
