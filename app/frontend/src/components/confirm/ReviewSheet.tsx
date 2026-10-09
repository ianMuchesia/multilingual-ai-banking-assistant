import { useId } from "react";
import { useBanking } from "../../banking/bankingContext";
import { findAssistant } from "../../utils/chatSelectors";
import { Sheet } from "../ui/Sheet";
import { ReviewForm } from "./ReviewForm";
import { SuccessState } from "./SuccessState";

/** Secure review sheet for the pending action of one assistant reply. */
export function ReviewSheet() {
  const { chat, accounts, reviewEntryId, closeReview, onActionExecuted, onActionCancelled } = useBanking();
  const titleId = useId();
  const entry = findAssistant(chat.entries, reviewEntryId);
  const action = entry?.response.pending_action ?? null;
  const open = entry !== null && action !== null && entry.actionStatus !== "cancelled";

  return (
    <Sheet open={open} onClose={closeReview} labelledBy={titleId} variant="modal">
      {entry && action && (
        <div className="sheet__content">
          {entry.actionStatus === "executed" && entry.actionResult ? (
            <SuccessState titleId={titleId} result={entry.actionResult} onDone={closeReview} />
          ) : (
            <ReviewForm
              key={entry.id}
              titleId={titleId}
              action={action}
              accounts={accounts.accounts}
              onExecuted={(result) => onActionExecuted(entry.id, result)}
              onCancelled={() => onActionCancelled(entry.id)}
            />
          )}
        </div>
      )}
    </Sheet>
  );
}
