import { Clock } from "lucide-react";
import { formatCountdown } from "../../hooks/useCountdown";

const WARNING_SECONDS = 30;

export function Countdown({ seconds }: { seconds: number }) {
  if (seconds <= 0) {
    return <span className="countdown countdown--expired">Expired</span>;
  }
  const warn = seconds <= WARNING_SECONDS;
  return (
    <span className={`countdown${warn ? " countdown--warning" : ""}`} title="Time left to confirm">
      <Clock size={14} aria-hidden="true" />
      <span className="visually-hidden">Expires in </span>
      {formatCountdown(seconds)}
    </span>
  );
}
