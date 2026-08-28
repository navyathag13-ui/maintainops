export type EquipmentStatus = "operational" | "down" | "maintenance";
export type PartUrgency = "none" | "watch" | "urgent";

export interface Equipment {
  id: number;
  name: string;
  type: string;
  location: string;
  current_location: string;
  status: EquipmentStatus;
  usage_hours: string;
  last_maintenance_usage_hours: string;
  maintenance_interval_hours: string;
  is_overdue: boolean;
  usage_count: number;
  max_usage_count: number | null;
  is_at_wear_limit: boolean;
  is_checked_out: boolean;
}

export interface EquipmentInput {
  name: string;
  type: string;
  location: string;
  status: EquipmentStatus;
  usage_hours: number;
  maintenance_interval_hours: number;
  max_usage_count: number | null;
}

export interface Part {
  id: number;
  name: string;
  sku: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  unit_cost: string;
  is_critical: boolean;
  is_low_stock: boolean;
  urgency: PartUrgency;
}

export interface PartInput {
  name: string;
  sku: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  unit_cost: number;
  is_critical: boolean;
}

export interface PartUsed {
  part_id: number;
  quantity: number;
  part_name: string | null;
  unit_cost_at_time: string;
}

export interface PartRestock {
  id: number;
  part_id: number;
  part_name: string | null;
  quantity: number;
  unit_cost: string;
  supplier: string | null;
  notes: string | null;
  restocked_at: string;
}

export interface PartRestockInput {
  quantity: number;
  unit_cost: number;
  supplier: string;
  notes: string;
}

export interface MaintenanceLog {
  id: number;
  equipment_id: number;
  performed_at: string;
  description: string;
  parts_used: PartUsed[];
}

export interface MaintenanceLogInput {
  equipment_id: number;
  description: string;
  parts_used: { part_id: number; quantity: number }[];
}

export interface EquipmentLoan {
  id: number;
  equipment_id: number;
  equipment_name: string | null;
  project: string;
  project_id: number | null;
  manager_name: string;
  borrower_name: string;
  borrower_employee_id: number | null;
  checked_out_at: string;
  expected_return_at: string;
  returned_at: string | null;
}

export interface EquipmentLoanInput {
  project_id: number;
  borrower_employee_id: number;
  expected_return_at: string;
}

export interface OverdueEquipment {
  id: number;
  name: string;
  location: string;
  usage_hours: string;
  last_maintenance_usage_hours: string;
  maintenance_interval_hours: string;
  hours_overdue: string;
}

export interface LowStockPart {
  id: number;
  name: string;
  sku: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  is_critical: boolean;
  urgency: PartUrgency;
}

export interface WearLimitReached {
  id: number;
  name: string;
  current_location: string;
  usage_count: number;
  max_usage_count: number;
}

export interface CostByEquipment {
  equipment_id: number;
  equipment_name: string;
  total_cost: string;
  maintenance_count: number;
}

export interface CostByMonth {
  month: string;
  total_cost: string;
}

export interface MaintenanceCostReport {
  total_cost: string;
  by_equipment: CostByEquipment[];
  by_month: CostByMonth[];
}

export interface SpendByPart {
  part_id: number;
  part_name: string;
  total_cost: string;
  total_quantity: number;
}

export interface SpendByMonth {
  month: string;
  total_cost: string;
}

export interface PartsSpendReport {
  total_cost: string;
  by_part: SpendByPart[];
  by_month: SpendByMonth[];
}

// --- Activity ---------------------------------------------------------------

export type ActivityEventType =
  | "equipment_checked_out"
  | "equipment_returned"
  | "maintenance_logged"
  | "part_used_on_project"
  | "part_restocked"
  | "project_created"
  | "employee_assigned"
  | "low_stock_reached";

export interface ActivityEvent {
  id: number;
  event_type: ActivityEventType;
  description: string;
  project_id: number | null;
  project_name: string | null;
  employee_id: number | null;
  employee_name: string | null;
  equipment_id: number | null;
  equipment_name: string | null;
  part_id: number | null;
  part_name: string | null;
  occurred_at: string;
}

// --- Employees ---------------------------------------------------------------

export type EmployeeRole = "manager" | "technician" | "equipment_operator" | "site_worker";

export interface Employee {
  id: number;
  name: string;
  role: EmployeeRole;
  active: boolean;
  created_at: string;
}

export interface EmployeeInput {
  name: string;
  role: EmployeeRole;
  active: boolean;
}

export interface EmployeeProjectRef {
  id: number;
  name: string;
  status: ProjectStatus;
}

export interface EmployeeEquipmentRef {
  id: number;
  name: string;
  project_name: string | null;
  expected_return_at: string;
}

export interface EmployeeDetail extends Employee {
  current_projects: EmployeeProjectRef[];
  borrowed_equipment: EmployeeEquipmentRef[];
  recent_activity: ActivityEvent[];
}

// --- Projects ---------------------------------------------------------------

export type ProjectStatus = "planning" | "active" | "on_hold" | "completed";

export interface ProjectInput {
  name: string;
  code?: string | null;
  description?: string | null;
  status: ProjectStatus;
  manager_id?: number | null;
  start_date?: string | null;
  expected_end_date?: string | null;
  location?: string | null;
}

export interface ProjectSummary {
  id: number;
  name: string;
  status: ProjectStatus;
  manager_id: number | null;
  manager_name: string | null;
  equipment_count: number;
  parts_used_count: number;
  worker_count: number;
  due_back_soon_count: number;
  maintenance_warning_count: number;
}

export interface ProjectTeamMember {
  id: number;
  name: string;
  role: EmployeeRole;
}

export interface ProjectEquipmentRef {
  id: number;
  name: string;
  type: string;
  is_overdue: boolean;
  current_location: string;
}

export interface ProjectPartUsage {
  id: number;
  part_id: number;
  part_name: string | null;
  quantity: number;
  unit_cost_at_time: string;
  employee_id: number | null;
  employee_name: string | null;
  used_at: string;
  note: string | null;
}

export interface ProjectPartUsageInput {
  parts_used: { part_id: number; quantity: number }[];
  employee_id: number | null;
  note: string;
}

export interface MaintenanceWarning {
  equipment_id: number;
  equipment_name: string;
  hours_overdue: string;
}

export interface ProjectDetail extends ProjectSummary {
  code: string | null;
  description: string | null;
  start_date: string | null;
  expected_end_date: string | null;
  location: string | null;
  created_at: string;
  team: ProjectTeamMember[];
  equipment_on_site: ProjectEquipmentRef[];
  parts_used: ProjectPartUsage[];
  maintenance_warnings: MaintenanceWarning[];
}

// --- Dashboard ---------------------------------------------------------------

export interface LocationCount {
  location: string;
  count: number;
}

export interface DueSoonItem {
  loan_id: number;
  equipment_id: number;
  equipment_name: string;
  project_name: string;
  expected_return_at: string;
  is_overdue_for_return: boolean;
}

export interface DashboardSummary {
  overdue_equipment: OverdueEquipment[];
  low_stock_parts: LowStockPart[];
  discard_recommended: WearLimitReached[];
  active_projects: ProjectSummary[];
  equipment_by_location: LocationCount[];
  due_soon: DueSoonItem[];
  recent_activity: ActivityEvent[];
}
