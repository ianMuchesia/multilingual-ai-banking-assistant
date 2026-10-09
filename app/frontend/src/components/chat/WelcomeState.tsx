import { brand } from "../../config";
import { AiAvatar } from "./AiAvatar";
import { ExampleChips } from "./ExampleChips";

export function WelcomeState({ onPick, disabled }: { onPick: (text: string) => void; disabled: boolean }) {
  return (
    <div className="welcome">
      <AiAvatar size={48} />
      <h2 className="welcome__title">Habari! I'm {brand.assistant}.</h2>
      <p className="welcome__line">Ask the way you would ask a friend at the counter.</p>
      <p className="label">Balances · statements · receipts · transfers · Lipa na M-Pesa</p>
      <ExampleChips onPick={onPick} disabled={disabled} />
    </div>
  );
}
