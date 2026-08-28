import type {
  Equipment,
  EquipmentInput,
  EquipmentLoan,
  EquipmentLoanInput,
  LowStockPart,
  MaintenanceLog,
  MaintenanceLogInput,
  OverdueEquipment,
  Part,
  PartInput,
  WearLimitReached,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  shortfalls?: { part_id: number; requested: number; available: number }[];
  activeLoanId?: number;

  constructor(status: number, message: string, extra?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.shortfalls = extra?.shortfalls as ApiError["shortfalls"];
    this.activeLoanId = extra?.active_loan_id as number | undefined;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? "Request failed", body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listEquipment: () => request<Equipment[]>("/equipment"),
  getEquipment: (id: number) => request<Equipment>(`/equipment/${id}`),
  createEquipment: (payload: EquipmentInput) =>
    request<Equipment>("/equipment", { method: "POST", body: JSON.stringify(payload) }),
  updateEquipment: (id: number, payload: Partial<EquipmentInput>) =>
    request<Equipment>(`/equipment/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteEquipment: (id: number) => request<void>(`/equipment/${id}`, { method: "DELETE" }),
  getEquipmentHistory: (id: number) => request<MaintenanceLog[]>(`/equipment/${id}/history`),
  getEquipmentLoans: (id: number) => request<EquipmentLoan[]>(`/equipment/${id}/loans`),
  checkOutEquipment: (id: number, payload: EquipmentLoanInput) =>
    request<EquipmentLoan>(`/equipment/${id}/checkout`, { method: "POST", body: JSON.stringify(payload) }),

  listEquipmentLoans: (active?: boolean) =>
    request<EquipmentLoan[]>(`/equipment-loans${active === undefined ? "" : `?active=${active}`}`),
  returnLoan: (loanId: number) => request<EquipmentLoan>(`/equipment-loans/${loanId}/return`, { method: "POST" }),

  listParts: () => request<Part[]>("/parts"),
  createPart: (payload: PartInput) =>
    request<Part>("/parts", { method: "POST", body: JSON.stringify(payload) }),
  updatePart: (id: number, payload: Partial<PartInput>) =>
    request<Part>(`/parts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletePart: (id: number) => request<void>(`/parts/${id}`, { method: "DELETE" }),

  createMaintenanceLog: (payload: MaintenanceLogInput) =>
    request<MaintenanceLog>("/maintenance-logs", { method: "POST", body: JSON.stringify(payload) }),

  getOverdueMaintenance: () => request<OverdueEquipment[]>("/alerts/overdue-maintenance"),
  getLowStock: () => request<LowStockPart[]>("/alerts/low-stock"),
  getDiscardRecommended: () => request<WearLimitReached[]>("/alerts/discard-recommended"),
};
