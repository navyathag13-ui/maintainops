export function WearLimitBadge({ usageCount, maxUsageCount }: { usageCount: number; maxUsageCount: number | null }) {
  if (maxUsageCount === null) return null;
  const atLimit = usageCount >= maxUsageCount;
  return (
    <span className={`badge badge-${atLimit ? "overdue" : "ok"}`}>
      {usageCount}/{maxUsageCount} uses{atLimit ? " -- discard" : ""}
    </span>
  );
}
