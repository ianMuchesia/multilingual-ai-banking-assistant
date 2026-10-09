import { useEffect, useState } from "react";

function secondsUntil(deadlineMs: number): number {
  if (Number.isNaN(deadlineMs)) return 0;
  return Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
}

/** Seconds remaining until `isoDeadline` (never negative), ticking once per second while active. */
export function useCountdown(isoDeadline: string, active = true): number {
  const deadlineMs = new Date(isoDeadline).getTime();
  const [remaining, setRemaining] = useState(() => secondsUntil(deadlineMs));

  useEffect(() => {
    if (!active) return undefined;
    setRemaining(secondsUntil(deadlineMs));
    const timer = window.setInterval(() => {
      const next = secondsUntil(deadlineMs);
      setRemaining(next);
      if (next <= 0) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [deadlineMs, active]);

  return remaining;
}

/** 125 -> "2:05" */
export function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
