// Low-level fetch wrapper: base URL, JSON, auth header, error normalisation, 401 handling.
import { config } from "../config";
import type { ErrorBody } from "../types/api";
import { getToken, setSession } from "./session";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type Method = "GET" | "POST";

interface RequestOptions {
  body?: unknown;
  /** Send the bearer token (default true). */
  auth?: boolean;
  /** On 401, clear the session so the router sends the user to /login (default true). */
  logoutOn401?: boolean;
}

function detailFrom(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null) return fallback;
  const { detail } = body as ErrorBody;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d.msg).filter((m): m is string => typeof m === "string");
    if (msgs.length) return msgs.join("; ");
  }
  return fallback;
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function request<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = true, logoutOn401 = true } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${config.apiBaseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }

  const data = await parseBody(res);

  if (!res.ok) {
    if (res.status === 401 && auth && logoutOn401) setSession(null);
    throw new ApiError(res.status, detailFrom(data, `Request failed (${res.status})`));
  }
  return data as T;
}
