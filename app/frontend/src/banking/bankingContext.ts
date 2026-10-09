import { createContext, useContext } from "react";
import type { AccountsState } from "../hooks/useAccounts";
import type { ChatState } from "../hooks/useChat";
import type { ConfirmResponse } from "../types/api";

/** App-wide banking state shared by the Home and Benki AI screens (survives navigation). */
export interface BankingContextValue {
  accounts: AccountsState;
  chat: ChatState;

  /** Composer text; quick actions prefill it, nothing is sent automatically. */
  draft: string;
  setDraft: (text: string) => void;
  /** Navigate to Benki AI, optionally prefilling the composer. */
  openAssistant: (prefill?: string) => void;
  /** Send a message and auto-open the review sheet if it created a pending action. */
  sendMessage: (text: string) => void;

  /** Assistant entry whose pending action is open in the review sheet. */
  reviewEntryId: string | null;
  openReview: (entryId: string) => void;
  closeReview: () => void;

  /** Assistant entry whose router decision is open in the "Why this answer?" drawer. */
  whyEntryId: string | null;
  openWhy: (entryId: string) => void;
  closeWhy: () => void;

  onActionExecuted: (entryId: string, result: ConfirmResponse) => void;
  onActionCancelled: (entryId: string) => void;

  hideAmounts: boolean;
  toggleHideAmounts: () => void;
}

export const BankingContext = createContext<BankingContextValue | null>(null);

export function useBanking(): BankingContextValue {
  const ctx = useContext(BankingContext);
  if (!ctx) throw new Error("useBanking must be used inside <BankingProvider>");
  return ctx;
}
