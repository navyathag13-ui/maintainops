import type {
  ActivityEvent,
  DashboardSummary,
  Employee,
  EmployeeDetail,
  EmployeeInput,
  Equipment,
  EquipmentInput,
  EquipmentLoan,
  EquipmentLoanInput,
  LowStockPart,
  MaintenanceCostReport,
  MaintenanceLog,
  MaintenanceLogInput,
  OverdueEquipment,
  Part,
  PartInput,
  PartRestock,
  PartRestockInput,
  PartsSpendReport,
  ProjectDetail,
  ProjectInput,
  ProjectPartUsage,
  ProjectPartUsageInput,
  ProjectSummary,
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
  restockPart: (id: number, payload: PartRestockInput) =>
    request<PartRestock>(`/parts/${id}/restock`, { method: "POST", body: JSON.stringify(payload) }),
  getPartRestocks: (id: number) => request<PartRestock[]>(`/parts/${id}/restocks`),

  createMaintenanceLog: (payload: MaintenanceLogInput) =>
    request<MaintenanceLog>("/maintenance-logs", { method: "POST", body: JSON.stringify(payload) }),

  getOverdueMaintenance: () => request<OverdueEquipment[]>("/alerts/overdue-maintenance"),
  getLowStock: () => request<LowStockPart[]>("/alerts/low-stock"),
  getDiscardRecommended: () => request<WearLimitReached[]>("/alerts/discard-recommended"),

  getMaintenanceCostReport: () => request<MaintenanceCostReport>("/reports/maintenance-cost"),
  getPartsSpendReport: () => request<PartsSpendReport>("/reports/parts-spend"),

  listProjects: () => request<ProjectSummary[]>("/projects"),
  getProject: (id: number) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (payload: ProjectInput) =>
    request<ProjectSummary>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: number, payload: Partial<ProjectInput>) =>
    request<ProjectDetail>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getProjectActivity: (id: number) => request<ActivityEvent[]>(`/projects/${id}/activity`),
  assignEmployeeToProject: (projectId: number, employeeId: number) =>
    request<{ project_id: number; employee_id: number }>(`/projects/${projectId}/employees`, {
      method: "POST",
      body: JSON.stringify({ employee_id: employeeId }),
    }),
  useProjectParts: (projectId: number, payload: ProjectPartUsageInput) =>
    request<ProjectPartUsage[]>(`/projects/${projectId}/parts-usage`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listEmployees: () => request<Employee[]>("/employees"),
  getEmployee: (id: number) => request<EmployeeDetail>(`/employees/${id}`),
  createEmployee: (payload: EmployeeInput) =>
    request<Employee>("/employees", { method: "POST", body: JSON.stringify(payload) }),
  updateEmployee: (id: number, payload: Partial<EmployeeInput>) =>
    request<Employee>(`/employees/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),

  listActivity: (limit = 50) => request<ActivityEvent[]>(`/activity?limit=${limit}`),

  getDashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
};
