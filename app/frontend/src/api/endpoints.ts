// Typed endpoint functions: one per route in the API contract.
import { config } from "../config";
import type {
  Account,
  CancelResponse,
  ChatResponse,
  ConfirmResponse,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  Me,
  Receipt,
  Slots,
  Transaction,
} from "../types/api";
import { request } from "./client";

export const api = {
  login: (body: LoginRequest) =>
    request<LoginResponse>("POST", "/auth/login", { body, auth: false }),

  me: () => request<Me>("GET", "/me"),

  accounts: () => request<Account[]>("GET", "/accounts"),

  transactions: (accountId?: number, limit: number = config.transactionsLimit) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (accountId !== undefined) params.set("account_id", String(accountId));
    return request<Transaction[]>("GET", `/transactions?${params.toString()}`);
  },

  receipt: (reference: string) =>
    request<Receipt>("GET", `/transactions/${encodeURIComponent(reference)}/receipt`),

  chat: (message: string) => request<ChatResponse>("POST", "/chat", { body: { message } }),

  confirmAction: (id: string, slots: Slots) =>
    request<ConfirmResponse>("POST", `/actions/${encodeURIComponent(id)}/confirm`, { body: { slots } }),

  cancelAction: (id: string) =>
    request<CancelResponse>("POST", `/actions/${encodeURIComponent(id)}/cancel`),

  health: () => request<HealthResponse>("GET", "/health", { auth: false }),
};
