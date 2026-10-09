import type { Route } from "../../types/api";

const LABELS: Record<Route, string> = {
  direct: "direct",
  confirm: "confirm",
  reject: "reject",
  llm: "llm",
};

export function RouteBadge({ route }: { route: Route }) {
  return (
    <span className={`route-badge route-badge--${route}`} title={`Route: ${route}`}>
      {LABELS[route]}
    </span>
  );
}
