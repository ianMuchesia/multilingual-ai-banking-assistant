import { CircleCheck, CircleX, LockKeyhole } from "lucide-react";
import { useCountdown } from "../../hooks/useCountdown";
import type { PendingAction } from "../../types/api";
import type { AssistantEntry } from "../../types/chat";
import { humanize } from "../../utils/format";
import { ReceiptCard } from "../replies/ReceiptCard";
import { Countdown } from "./Countdown";

interface Props {
  entry: AssistantEntry;
  action: PendingAction;
  onReview: () => void;
}

/** In-chat card for a money-moving request: status plus a button to open the review sheet. */
export function ActionSummary({ entry, action, onReview }: Props) {
  const status = entry.actionStatus ?? "pending";
  const remaining = useCountdown(action.expires_at, status === "pending");

  if (status === "executed" && entry.actionResult) {
    return (
      <div className="action-card action-card--done">
        <p className="action-card__status">
          <CircleCheck size={16} aria-hidden="true" /> Confirmed and sent
        </p>
        <ReceiptCard receipt={entry.actionResult.receipt} />
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="action-card action-card--cancelled">
        <p className="action-card__status">
          <CircleX size={16} aria-hidden="true" /> Cancelled. Nothing was sent.
        </p>
      </div>
    );
  }

  const expired = remaining <= 0;
  return (
    <div className="action-card">
      <div className="action-card__row">
        <span className="review__lock review__lock--sm" aria-hidden="true">
          <LockKeyhole size={16} />
        </span>
        <div className="action-card__text">
          <p className="action-card__title">{humanize(action.intent)}</p>
          <p className="label">
            {action.missing_slots.length > 0
              ? `${action.missing_slots.length} detail${action.missing_slots.length === 1 ? "" : "s"} needed`
              : "Ready for your review"}
          </p>
        </div>
        <Countdown seconds={remaining} />
      </div>
      <button type="button" className="btn btn--primary btn--block" onClick={onReview} disabled={expired}>
        {expired ? "Expired" : "Review and confirm"}
      </button>
    </div>
  );
}
