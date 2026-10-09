import { useCallback, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { AssistantEntry, ChatEntry } from "../types/chat";

export type AssistantPatch = Partial<Pick<AssistantEntry, "actionStatus" | "actionResult">>;

export interface ChatState {
  entries: ChatEntry[];
  sending: boolean;
  selectedId: string | null;
  send: (message: string) => Promise<AssistantEntry | null>;
  select: (entryId: string) => void;
  updateAssistant: (entryId: string, patch: AssistantPatch) => void;
}

export function useChat(): ChatState {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [sending, setSending] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const counter = useRef(0);

  const nextId = () => {
    counter.current += 1;
    return `m${counter.current}`;
  };

  const send = useCallback(async (message: string) => {
    const text = message.trim();
    if (!text) return null;
    setEntries((prev) => [...prev, { id: nextId(), role: "user", text }]);
    setSending(true);
    try {
      const response = await api.chat(text);
      const id = nextId();
      const entry: AssistantEntry = {
        id,
        role: "assistant",
        response,
        actionStatus: response.pending_action ? "pending" : undefined,
      };
      setEntries((prev) => [...prev, entry]);
      setSelectedId(id);
      return entry;
    } catch (e) {
      const detail = e instanceof ApiError ? e.detail : "Something went wrong.";
      setEntries((prev) => [...prev, { id: nextId(), role: "error", text: detail }]);
      return null;
    } finally {
      setSending(false);
    }
  }, []);

  const updateAssistant = useCallback((entryId: string, patch: AssistantPatch) => {
    setEntries((prev) =>
      prev.map((e) => (e.id === entryId && e.role === "assistant" ? { ...e, ...patch } : e)),
    );
  }, []);

  return { entries, sending, selectedId, send, select: setSelectedId, updateAssistant };
}
