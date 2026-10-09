import { useEffect, useState } from "react";
import { api } from "../api/endpoints";
import type { HealthResponse } from "../types/api";

/** Fetches /api/health once; null while loading or if the backend is unreachable. */
export function useHealth(): HealthResponse | null {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth(null));
    return () => {
      alive = false;
    };
  }, []);

  return health;
}
