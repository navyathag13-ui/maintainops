import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toast } from "./Toast";

describe("Toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows its message", () => {
    render(<Toast message="Saved" onDismiss={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
  });

  it("dismisses itself after 4 seconds", () => {
    const onDismiss = vi.fn();
    render(<Toast message="Saved" onDismiss={onDismiss} />);
    act(() => vi.advanceTimersByTime(3999));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(2));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("does not restart the countdown when the parent re-renders with a new onDismiss", () => {
    // Regression: the timer used to depend on onDismiss, which is a fresh
    // function on every parent render, so any re-render reset the 4 s countdown.
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(<Toast message="Saved" onDismiss={first} />);
    act(() => vi.advanceTimersByTime(3000));
    rerender(<Toast message="Saved" onDismiss={second} />);
    act(() => vi.advanceTimersByTime(1100));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1); // the latest callback runs, on the original schedule
  });

  it("restarts the countdown when the message changes", () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<Toast message="One" onDismiss={onDismiss} />);
    act(() => vi.advanceTimersByTime(3000));
    rerender(<Toast message="Two" onDismiss={onDismiss} />);
    act(() => vi.advanceTimersByTime(3000));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1100));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
