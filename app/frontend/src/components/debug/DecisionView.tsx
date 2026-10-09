import type { Decision } from "../../types/api";
import { formatScore } from "../../utils/format";
import { NearestExamples } from "./NearestExamples";
import { RouteBadge } from "./RouteBadge";
import { ScoreBars } from "./ScoreBars";

const ROUTE_EXPLAINER: Record<Decision["route"], string> = {
  direct: "Confident and read-only, so the answer was shown immediately.",
  confirm: "Moves money, so nothing happens until you review and confirm.",
  reject: "Recognised as something this assistant does not support.",
  llm: "Not confident enough to act; would be handed to an LLM.",
};

/** Full explanation of one router decision. */
export function DecisionView({ decision, message }: { decision: Decision; message: string }) {
  return (
    <div className="decision">
      {message && (
        <figure className="decision__message">
          <figcaption className="label">You said</figcaption>
          <blockquote>{message}</blockquote>
        </figure>
      )}

      <div className="decision__route">
        <RouteBadge route={decision.route} />
        <p>{ROUTE_EXPLAINER[decision.route]}</p>
      </div>

      <dl className="stat-grid">
        <div className="stat">
          <dt className="label">Intent</dt>
          <dd className="mono">{decision.intent}</dd>
        </div>
        <div className="stat">
          <dt className="label">Score</dt>
          <dd className="mono">{formatScore(decision.score)}</dd>
        </div>
        <div className="stat">
          <dt className="label">Margin</dt>
          <dd className="mono">{formatScore(decision.margin)}</dd>
        </div>
        <div className="stat">
          <dt className="label">Latency</dt>
          <dd className="mono">{decision.latency_ms.toFixed(1)} ms</dd>
        </div>
      </dl>

      <section className="decision__section" aria-labelledby="why-top3">
        <h3 id="why-top3" className="label">
          Top-3 intents
        </h3>
        <ScoreBars top3={decision.top3} chosen={decision.intent} />
      </section>

      <section className="decision__section" aria-labelledby="why-nearest">
        <h3 id="why-nearest" className="label">
          Nearest training examples
        </h3>
        <NearestExamples examples={decision.nearest_examples} />
      </section>

      <section className="decision__section" aria-labelledby="why-reasons">
        <h3 id="why-reasons" className="label">
          Reasons
        </h3>
        {decision.reasons.length > 0 ? (
          <ul className="reasons">
            {decision.reasons.map((r, i) => (
              <li key={`${i}-${r}`}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No reasons given.</p>
        )}
      </section>
    </div>
  );
}
