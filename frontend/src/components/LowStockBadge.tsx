export function LowStockBadge({ isLowStock }: { isLowStock: boolean }) {
  if (!isLowStock) return <span className="badge badge-ok">In stock</span>;
  return <span className="badge badge-overdue">Low stock</span>;
}
