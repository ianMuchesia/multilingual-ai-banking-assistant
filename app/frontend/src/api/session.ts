// Auth session: kept in memory and mirrored to sessionStorage so a reload keeps you logged in.
import { config } from "../config";
import type { User } from "../types/api";

export interface Session {
  token: string;
  user: User;
}

type Listener = (session: Session | null) => void;

let current: Session | null = readStored();
const listeners = new Set<Listener>();

function isSession(value: unknown): value is Session {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.token === "string" && typeof v.user === "object" && v.user !== null;
}

function readStored(): Session | null {
  try {
    const raw = sessionStorage.getItem(config.sessionStorageKey);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function getSession(): Session | null {
  return current;
}

export function getToken(): string | null {
  return current?.token ?? null;
}

export function setSession(session: Session | null): void {
  current = session;
  try {
    if (session) sessionStorage.setItem(config.sessionStorageKey, JSON.stringify(session));
    else sessionStorage.removeItem(config.sessionStorageKey);
  } catch {
    // storage unavailable (private mode etc.): in-memory session still works
  }
  listeners.forEach((l) => l(session));
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
