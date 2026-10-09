import { ArrowLeftRight, FileText, House, Sparkles, Wallet, type LucideIcon } from "lucide-react";
import { brand, prompts, routes } from "../../config";

export type NavItem =
  | { kind: "link"; label: string; icon: LucideIcon; to: string; ai?: boolean }
  | { kind: "prompt"; label: string; icon: LucideIcon; prompt: string };

/** Only Home and Benki AI are real screens; the rest open Benki AI with a prefilled prompt. */
export const navItems: NavItem[] = [
  { kind: "link", label: "Home", icon: House, to: routes.home },
  { kind: "prompt", label: "Accounts", icon: Wallet, prompt: prompts.balances },
  { kind: "prompt", label: "Payments", icon: ArrowLeftRight, prompt: prompts.payBill },
  { kind: "prompt", label: "Statements", icon: FileText, prompt: prompts.statement },
  { kind: "link", label: brand.assistant, icon: Sparkles, to: routes.assistant, ai: true },
];
