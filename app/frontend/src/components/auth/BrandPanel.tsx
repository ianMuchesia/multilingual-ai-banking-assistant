import { Languages, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";
import { brand } from "../../config";
import { Logo } from "../brand/Logo";

const FEATURES: { icon: LucideIcon; title: string; line: string }[] = [
  { icon: ShieldCheck, title: "Secure by design", line: "Money only moves after you review and confirm." },
  { icon: Languages, title: "Multilingual", line: "English, Kiswahili and Sheng, the way you speak." },
  { icon: Sparkles, title: `${brand.assistant} assistant`, line: "Balances, statements and payments in a sentence." },
];

/** Left half of the login screen: brand, tagline and three feature points. */
export function BrandPanel() {
  return (
    <section className="brand-panel" aria-label={`About ${brand.name}`}>
      <span className="brand-panel__band" aria-hidden="true" />
      <Logo size={36} />
      <p className="brand-panel__tagline">{brand.tagline}</p>
      <ul className="brand-panel__features">
        {FEATURES.map(({ icon: Icon, title, line }) => (
          <li key={title} className="feature">
            <span className="feature__icon" aria-hidden="true">
              <Icon size={18} />
            </span>
            <span>
              <span className="feature__title">{title}</span>
              <span className="feature__line">{line}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="label brand-panel__foot">A simulation for teaching intent routing. Not a real bank.</p>
    </section>
  );
}
