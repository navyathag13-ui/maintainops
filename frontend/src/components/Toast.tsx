import { useEffect, useRef } from "react";
import { CheckIcon } from "./icons";

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  // Only `message` should restart the timer -- onDismiss is a fresh
  // function on every parent render, and depending on it directly would
  // reset the 4s countdown on any unrelated re-render while the toast
  // is showing.
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  useEffect(() => {
    const timer = setTimeout(() => onDismissRef.current(), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <div className="toast" role="status">
      <CheckIcon />
      {message}
    </div>
  );
}
