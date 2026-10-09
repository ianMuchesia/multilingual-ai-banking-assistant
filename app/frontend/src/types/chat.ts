import type { ChatResponse, ConfirmResponse } from "./api";

export type ActionStatus = "pending" | "executed" | "cancelled";

export interface UserEntry {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantEntry {
  id: string;
  role: "assistant";
  response: ChatResponse;
  actionStatus?: ActionStatus;
  actionResult?: ConfirmResponse;
}

export interface ErrorEntry {
  id: string;
  role: "error";
  text: string;
}

export type ChatEntry = UserEntry | AssistantEntry | ErrorEntry;
