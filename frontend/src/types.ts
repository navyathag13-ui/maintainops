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
  manager_name: string;
  borrower_name: string;
  checked_out_at: string;
  expected_return_at: string;
  returned_at: string | null;
}

export interface EquipmentLoanInput {
  project: string;
  manager_name: string;
  borrower_name: string;
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
