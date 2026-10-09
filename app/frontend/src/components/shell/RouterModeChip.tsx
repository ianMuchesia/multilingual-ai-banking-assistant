import type { HealthResponse } from "../../types/api";

const MODE_LABEL: Record<HealthResponse["router_mode"], string> = {
  gemma: "Gemma router",
  stub: "stub router",
};

/** Subtle "Demo · stub router" chip from GET /api/health. */
export function RouterModeChip({ health }: { health: HealthResponse | null }) {
  const text = health ? `Demo · ${MODE_LABEL[health.router_mode] ?? health.router_mode}` : "Demo · backend offline";
  return (
    <span className={`router-chip${health ? "" : " router-chip--down"}`} title="Intent router mode reported by /api/health">
      {text}
    </span>
  );
}
