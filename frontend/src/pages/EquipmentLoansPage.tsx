import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { CheckOutForm } from "../components/CheckOutForm";
import { EmptyState } from "../components/EmptyState";
import { Toast } from "../components/Toast";
import type { EquipmentLoan } from "../types";
import { formatDate } from "../utils";

export function EquipmentLoansPage() {
  const [loans, setLoans] = useState<EquipmentLoan[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [returningId, setReturningId] = useState<number | null>(null);

  function refresh() {
    return api.listEquipmentLoans(true).then(setLoans);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleReturn(loan: EquipmentLoan) {
    setReturningId(loan.id);
    try {
      await api.returnLoan(loan.id);
      // Awaited: the returned loan needs to be out of `loans` before the
      // button re-enables, or a fast second click could return it again.
      await refresh();
      setToast(`${loan.equipment_name ?? "Equipment"} returned -- back at its home location.`);
    } finally {
      setReturningId(null);
    }
  }

  return (
    <div>
      <h1>Borrowed Equipment</h1>
      <p className="subtitle">Who has what, for which project, and when it's due back.</p>

      {!showForm && <button onClick={() => setShowForm(true)}>Check Out Equipment</button>}

      {showForm && (
        <CheckOutForm
          onCancel={() => setShowForm(false)}
          onSuccess={(loan) => {
            setShowForm(false);
            refresh();
            setToast(`${loan.equipment_name ?? "Equipment"} checked out to ${loan.borrower_name}.`);
          }}
        />
      )}

      <div style={{ marginTop: "1.5rem" }}>
        {loans === null ? (
          <p>Loading...</p>
        ) : loans.length === 0 ? (
          <EmptyState
            title="Nothing checked out right now"
            description="Everything's at its home location."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Equipment</th>
                  <th>Project</th>
                  <th>Manager</th>
                  <th>Borrower</th>
                  <th>Expected return</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => (
                  <tr key={loan.id}>
                    <td>
                      <Link to={`/equipment/${loan.equipment_id}`}>{loan.equipment_name ?? `#${loan.equipment_id}`}</Link>
                    </td>
                    <td>{loan.project}</td>
                    <td>{loan.manager_name}</td>
                    <td>{loan.borrower_name}</td>
                    <td>{formatDate(loan.expected_return_at)}</td>
                    <td>
                      <button type="button" onClick={() => handleReturn(loan)} disabled={returningId === loan.id}>
                        {returningId === loan.id ? "Returning..." : "Return"}
                      </button>
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
