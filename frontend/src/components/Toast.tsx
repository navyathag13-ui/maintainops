import { useEffect } from "react";
import { CheckIcon } from "./icons";

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [message, onDismiss]);

  return (
    <div className="toast" role="status">
      <CheckIcon />
      {message}
    </div>
  );
}
