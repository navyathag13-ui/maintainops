import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { CheckOutForm } from "../components/CheckOutForm";
import { EmptyState } from "../components/EmptyState";
import { LogMaintenanceForm } from "../components/LogMaintenanceForm";
import { MaintenanceStatusBadge } from "../components/MaintenanceStatusBadge";
import { Toast } from "../components/Toast";
import { WearLimitBadge } from "../components/WearLimitBadge";
import type { Equipment, EquipmentLoan, MaintenanceLog } from "../types";
import { formatDate, formatDateTime, formatHours } from "../utils";

export function EquipmentDetailPage() {
  const { id } = useParams();
  const equipmentId = Number(id);
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [history, setHistory] = useState<MaintenanceLog[] | null>(null);
  const [loans, setLoans] = useState<EquipmentLoan[] | null>(null);
  const [showMaintenanceForm, setShowMaintenanceForm] = useState(false);
  const [showCheckoutForm, setShowCheckoutForm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);

  function refresh() {
    api.getEquipment(equipmentId).then(setEquipment);
    api.getEquipmentHistory(equipmentId).then(setHistory);
    api.getEquipmentLoans(equipmentId).then(setLoans);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [equipmentId]);

  if (!equipment) return <p>Loading...</p>;

  const activeLoan = loans?.find((l) => l.returned_at === null) ?? null;

  async function handleReturn() {
    if (!activeLoan) return;
    setReturning(true);
    try {
      await api.returnLoan(activeLoan.id);
      setToast(`Returned -- back at ${equipment!.location}.`);
      refresh();
    } finally {
      setReturning(false);
    }
  }

  return (
    <div>
      <Link to="/equipment" className="back-link">
        &larr; Back to equipment
      </Link>
      <h1>{equipment.name}</h1>
      <dl className="equipment-detail-grid">
        <dt>Type</dt>
        <dd>{equipment.type}</dd>
        <dt>Home location</dt>
        <dd>{equipment.location}</dd>
        <dt>Current location</dt>
        <dd>{equipment.current_location}</dd>
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
        {equipment.max_usage_count !== null && (
          <>
            <dt>Wear limit</dt>
            <dd>
              <WearLimitBadge usageCount={equipment.usage_count} maxUsageCount={equipment.max_usage_count} />
            </dd>
          </>
        )}
      </dl>

      {activeLoan && (
        <div className="loan-banner">
          Checked out to <strong>{activeLoan.borrower_name}</strong> for <strong>{activeLoan.project}</strong>,
          due back {formatDate(activeLoan.expected_return_at)} (manager: {activeLoan.manager_name}).
        </div>
      )}

      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
        {!showMaintenanceForm && <button onClick={() => setShowMaintenanceForm(true)}>Log Maintenance</button>}
        {!showCheckoutForm && !activeLoan && <button onClick={() => setShowCheckoutForm(true)}>Check Out</button>}
        {activeLoan && (
          <button type="button" onClick={handleReturn} disabled={returning}>
            {returning ? "Returning..." : "Return"}
          </button>
        )}
      </div>

      {showMaintenanceForm && (
        <LogMaintenanceForm
          equipmentId={equipment.id}
          onCancel={() => setShowMaintenanceForm(false)}
          onSuccess={() => {
            setShowMaintenanceForm(false);
            refresh();
            setToast(`Maintenance logged for ${equipment.name}.`);
          }}
        />
      )}

      {showCheckoutForm && (
        <CheckOutForm
          equipmentId={equipment.id}
          equipmentName={equipment.name}
          onCancel={() => setShowCheckoutForm(false)}
          onSuccess={(loan) => {
            setShowCheckoutForm(false);
            refresh();
            setToast(`Checked out to ${loan.borrower_name} for ${loan.project}.`);
          }}
        />
      )}

      <h2>Maintenance history</h2>
      {history === null ? (
        <p>Loading...</p>
      ) : history.length === 0 ? (
        <EmptyState
          title="No maintenance logged yet"
          description="Once you log the first service, it'll show up here with a full parts trail."
        />
      ) : (
        <div className="table-scroll">
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
        </div>
      )}

      <h2>Borrow history</h2>
      {loans === null ? (
        <p>Loading...</p>
      ) : loans.length === 0 ? (
        <EmptyState title="Never been borrowed" description="It's stayed at its home location so far." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Project</th>
                <th>Borrower</th>
                <th>Checked out</th>
                <th>Expected return</th>
                <th>Returned</th>
              </tr>
            </thead>
            <tbody>
              {loans.map((loan) => (
                <tr key={loan.id}>
                  <td>{loan.project}</td>
                  <td>{loan.borrower_name}</td>
                  <td>{formatDateTime(loan.checked_out_at)}</td>
                  <td>{formatDate(loan.expected_return_at)}</td>
                  <td>{loan.returned_at ? formatDateTime(loan.returned_at) : "-- still out"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
