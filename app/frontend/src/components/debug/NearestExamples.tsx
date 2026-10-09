import type { NearestExample } from "../../types/api";
import { formatScore } from "../../utils/format";

export function NearestExamples({ examples }: { examples: NearestExample[] }) {
  if (examples.length === 0) return <p className="muted">None returned.</p>;
  return (
    <ul className="nearest">
      {examples.map(([text, intent, score], i) => (
        <li key={`${i}-${text}`} className="nearest__item">
          <p className="nearest__text">“{text}”</p>
          <p className="nearest__meta label">
            {intent} · sim {formatScore(score)}
          </p>
        </li>
      ))}
    </ul>
  );
}
