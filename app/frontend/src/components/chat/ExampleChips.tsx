import { exampleMessages, type Lang } from "../../config";

const LANG_LABEL: Record<Lang, string> = { en: "EN", sw: "SW", sheng: "SHENG" };

interface Props {
  onPick: (text: string) => void;
  disabled?: boolean;
}

export function ExampleChips({ onPick, disabled = false }: Props) {
  return (
    <ul className="chips" aria-label="Example messages">
      {exampleMessages.map((ex) => (
        <li key={ex.text}>
          <button type="button" className="chip" disabled={disabled} onClick={() => onPick(ex.text)}>
            <span className="chip__lang">{LANG_LABEL[ex.lang]}</span>
            {ex.text}
          </button>
        </li>
      ))}
    </ul>
  );
}
