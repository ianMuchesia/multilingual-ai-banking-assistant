import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { routes } from "../config";
import { useAccounts } from "../hooks/useAccounts";
import { useChat } from "../hooks/useChat";
import { useToast } from "../toast/toastContext";
import type { ConfirmResponse } from "../types/api";
import { formatKES } from "../utils/format";
import { BankingContext, type BankingContextValue } from "./bankingContext";

export function BankingProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { notify } = useToast();
  const accounts = useAccounts();
  const chat = useChat();
  const { refresh } = accounts;
  const { send, updateAssistant } = chat;

  const [draft, setDraft] = useState("");
  const [reviewEntryId, setReviewEntryId] = useState<string | null>(null);
  const [whyEntryId, setWhyEntryId] = useState<string | null>(null);
  const [hideAmounts, setHideAmounts] = useState(false);

  const openAssistant = useCallback(
    (prefill?: string) => {
      if (prefill !== undefined) setDraft(prefill);
      navigate(routes.assistant);
    },
    [navigate],
  );

  const sendMessage = useCallback(
    (text: string) => {
      void send(text).then((entry) => {
        if (entry?.response.pending_action) setReviewEntryId(entry.id);
      });
    },
    [send],
  );

  const onActionExecuted = useCallback(
    (entryId: string, result: ConfirmResponse) => {
      updateAssistant(entryId, { actionStatus: "executed", actionResult: result });
      notify("success", `Sent ${formatKES(result.receipt.amount)} · Ref ${result.receipt.reference}`);
      void refresh();
    },
    [updateAssistant, notify, refresh],
  );

  const onActionCancelled = useCallback(
    (entryId: string) => {
      updateAssistant(entryId, { actionStatus: "cancelled" });
      setReviewEntryId(null);
      notify("info", "Cancelled. Nothing was sent.");
    },
    [updateAssistant, notify],
  );

  const value = useMemo<BankingContextValue>(
    () => ({
      accounts,
      chat,
      draft,
      setDraft,
      openAssistant,
      sendMessage,
      reviewEntryId,
      openReview: setReviewEntryId,
      closeReview: () => setReviewEntryId(null),
      whyEntryId,
      openWhy: setWhyEntryId,
      closeWhy: () => setWhyEntryId(null),
      onActionExecuted,
      onActionCancelled,
      hideAmounts,
      toggleHideAmounts: () => setHideAmounts((h) => !h),
    }),
    [accounts, chat, draft, openAssistant, sendMessage, reviewEntryId, whyEntryId, onActionExecuted, onActionCancelled, hideAmounts],
  );

  return <BankingContext.Provider value={value}>{children}</BankingContext.Provider>;
}
