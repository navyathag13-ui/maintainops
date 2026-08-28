import type { ReactNode } from "react";
import { ClipboardIcon } from "./icons";

export function EmptyState({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="empty-state">
      <ClipboardIcon />
      <strong>{title}</strong>
      {description && <p>{description}</p>}
    </div>
  );
}
