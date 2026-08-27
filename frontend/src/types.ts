export type EquipmentStatus = "operational" | "down" | "maintenance";

export interface Equipment {
  id: number;
  name: string;
  type: string;
  location: string;
  status: EquipmentStatus;
  usage_hours: string;
  last_maintenance_usage_hours: string;
  maintenance_interval_hours: string;
  is_overdue: boolean;
}

export interface EquipmentInput {
  name: string;
  type: string;
  location: string;
  status: EquipmentStatus;
  usage_hours: number;
  maintenance_interval_hours: number;
}

export interface Part {
  id: number;
  name: string;
  sku: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  unit_cost: string;
  is_low_stock: boolean;
}

export interface PartInput {
  name: string;
  sku: string;
  quantity_on_hand: number;
  reorder_threshold: number;
  unit_cost: number;
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
}
