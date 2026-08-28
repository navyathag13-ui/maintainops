import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Employee } from "../types";

const ROLE_LABELS: Record<string, string> = {
  manager: "Manager",
  technician: "Technician",
  equipment_operator: "Equipment Operator",
  site_worker: "Site Worker",
};

export function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[] | null>(null);

  useEffect(() => {
    api.listEmployees().then(setEmployees);
  }, []);

  return (
    <div>
      <h1>Employees</h1>
      <p className="subtitle">Who's who, for managers, borrowers, and project teams.</p>
      {employees === null ? (
        <p>Loading...</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id}>
                  <td>
                    <Link to={`/employees/${emp.id}`}>{emp.name}</Link>
                  </td>
                  <td>{ROLE_LABELS[emp.role] ?? emp.role}</td>
                  <td>
                    <span className={`badge badge-${emp.active ? "ok" : "neutral"}`}>
                      {emp.active ? "Active" : "Inactive"}
                    </span>
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
