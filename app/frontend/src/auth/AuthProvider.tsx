import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/endpoints";
import { getSession, setSession, subscribe, type Session } from "../api/session";
import { AuthContext, type AuthContextValue } from "./authContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setState] = useState<Session | null>(getSession);

  // Session can also be cleared by the API client on a 401.
  useEffect(() => subscribe(setState), []);

  // A token restored from sessionStorage may have expired: validate it once via /me.
  // A 401 clears the session (see api/client), which sends the user back to /login.
  useEffect(() => {
    const restored = getSession();
    if (!restored) return;
    api
      .me()
      .then((me) => {
        const latest = getSession();
        if (latest && latest.token === restored.token) {
          setSession({ token: latest.token, user: { id: me.id, username: me.username, full_name: me.full_name } });
        }
      })
      .catch(() => undefined);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login({ username, password });
    setSession({ token: res.access_token, user: res.user });
  }, []);

  const logout = useCallback(() => setSession(null), []);

  const value = useMemo<AuthContextValue>(() => ({ session, login, logout }), [session, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
