import type { AssistantEntry, ChatEntry } from "../types/chat";

export function findAssistant(entries: ChatEntry[], id: string | null): AssistantEntry | null {
  if (!id) return null;
  const entry = entries.find((e) => e.id === id);
  return entry && entry.role === "assistant" ? entry : null;
}

/** The user message that produced the given assistant entry. */
export function promptFor(entries: ChatEntry[], assistantId: string): string {
  const index = entries.findIndex((e) => e.id === assistantId);
  for (let i = index - 1; i >= 0; i -= 1) {
    const prev = entries[i];
    if (prev.role === "user") return prev.text;
  }
  return "";
}
