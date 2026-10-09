import { useId } from "react";
import { useBanking } from "../../banking/bankingContext";
import { brand } from "../../config";
import { findAssistant, promptFor } from "../../utils/chatSelectors";
import { Sheet } from "../ui/Sheet";
import { DecisionView } from "./DecisionView";

/** "Why this answer?": the intent router's decision for one reply (side drawer / bottom sheet). */
export function WhyDrawer() {
  const { chat, whyEntryId, closeWhy } = useBanking();
  const titleId = useId();
  const entry = findAssistant(chat.entries, whyEntryId);

  return (
    <Sheet open={entry !== null} onClose={closeWhy} labelledBy={titleId} variant="drawer" className="sheet--ai">
      {entry && (
        <div className="sheet__content">
          <p className="label label--ai">
            <span className="ai-badge">AI</span> {brand.assistant} · router debug
          </p>
          <h2 id={titleId} className="sheet__title">
            Why this answer?
          </h2>
          <DecisionView decision={entry.response.decision} message={promptFor(chat.entries, entry.id)} />
        </div>
      )}
    </Sheet>
  );
}
