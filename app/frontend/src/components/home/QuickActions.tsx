import { FileText, Receipt, SendHorizontal, Smartphone, type LucideIcon } from "lucide-react";
import { prompts } from "../../config";

const ACTIONS: { label: string; icon: LucideIcon; prompt: string }[] = [
  { label: "Send money", icon: SendHorizontal, prompt: prompts.send },
  { label: "Pay bill / till", icon: Smartphone, prompt: prompts.payBill },
  { label: "Get statement", icon: FileText, prompt: prompts.statement },
  { label: "Receipts", icon: Receipt, prompt: prompts.receipts },
];

/** Each action opens Benki AI with a prefilled message; nothing is sent until the user presses Send. */
export function QuickActions({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <section aria-labelledby="quick-title">
      <h2 id="quick-title" className="section-title">
        Quick actions
      </h2>
      <ul className="quick-actions">
        {ACTIONS.map(({ label, icon: Icon, prompt }) => (
          <li key={label}>
            <button type="button" className="quick-action" onClick={() => onPick(prompt)}>
              <span className="quick-action__icon" aria-hidden="true">
                <Icon size={20} />
              </span>
              <span className="quick-action__label">{label}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
