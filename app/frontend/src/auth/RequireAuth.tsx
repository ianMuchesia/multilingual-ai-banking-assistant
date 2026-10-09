import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { routes } from "../config";
import { useAuth } from "./authContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to={routes.login} replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
