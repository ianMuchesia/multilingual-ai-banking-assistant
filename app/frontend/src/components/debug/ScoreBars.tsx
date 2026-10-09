import type { IntentScore } from "../../types/api";
import { formatScore } from "../../utils/format";

/** Horizontal bars for the top-3 intent scores (probabilities 0..1). */
export function ScoreBars({ top3, chosen }: { top3: IntentScore[]; chosen: string }) {
  return (
    <ol className="score-bars">
      {top3.map(([intent, score]) => {
        const pct = Math.max(0, Math.min(1, score)) * 100;
        return (
          <li key={intent} className={`score-bars__row${intent === chosen ? " score-bars__row--chosen" : ""}`}>
            <div className="score-bars__labels mono">
              <span>{intent}</span>
              <span>{formatScore(score)}</span>
            </div>
            <div
              className="score-bars__track"
              role="meter"
              aria-label={`${intent} score`}
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={Number(score.toFixed(3))}
            >
              <div className="score-bars__fill" style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
