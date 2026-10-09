import { LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/authContext";
import { BrandPanel } from "../components/auth/BrandPanel";
import { DemoUsersNote } from "../components/auth/DemoUsersNote";
import { ThemeToggle } from "../components/shell/ThemeToggle";
import { InlineError } from "../components/ui/InlineError";
import { routes } from "../config";

function redirectTarget(state: unknown): string {
  if (typeof state === "object" && state !== null && "from" in state) {
    const from = (state as { from: unknown }).from;
    if (typeof from === "string" && from.startsWith("/") && from !== routes.login) return from;
  }
  return routes.home;
}

export function LoginPage() {
  const { session, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (session) return <Navigate to={routes.home} replace />;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(redirectTarget(location.state), { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("That username and password don't match.");
      else setError(err instanceof ApiError ? err.detail : "Sign-in failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const fillDemo = (user: string, pass: string) => {
    setUsername(user);
    setPassword(pass);
    setError(null);
  };

  return (
    <div className="login">
      <BrandPanel />
      <main className="login__main">
        <div className="login__toggle">
          <ThemeToggle />
        </div>
        <div className="login__card">
          <p className="label">Online banking</p>
          <h1 className="login__title">Sign in</h1>

          <form className="login__form" onSubmit={(e) => void handleSubmit(e)}>
            <div className="field">
              <label htmlFor="username" className="field__label">
                Username
              </label>
              <input
                id="username"
                className="input"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="password" className="field__label">
                Password
              </label>
              <input
                id="password"
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <InlineError message={error} />}
            <button
              type="submit"
              className="btn btn--primary btn--block btn--lg"
              disabled={submitting || !username || !password}
            >
              <LockKeyhole size={16} aria-hidden="true" />
              {submitting ? "Signing in…" : "Sign in securely"}
            </button>
          </form>

          <DemoUsersNote onPick={fillDemo} />
        </div>
      </main>
    </div>
  );
}
