import { Landmark, Wallet } from "lucide-react";
import type { Account } from "../../types/api";
import { humanize, maskAccount } from "../../utils/format";
import { Money } from "../ui/Money";

interface Props {
  account: Account;
  hidden?: boolean;
  compact?: boolean;
}

export function AccountCard({ account, hidden = false, compact = false }: Props) {
  const Icon = account.type === "savings" ? Landmark : Wallet;
  return (
    <article className={`account-card${compact ? " account-card--compact" : ""}`}>
      <div className="account-card__head">
        <span className="account-card__icon" aria-hidden="true">
          <Icon size={16} />
        </span>
        <span className="account-card__type">{humanize(account.type)}</span>
        <span className="account-card__number label" title={hidden ? undefined : account.number}>
          {maskAccount(account.number)}
        </span>
      </div>
      <p className="account-card__balance">
        <span className="visually-hidden">Available balance: </span>
        <Money amount={account.balance} hidden={hidden} />
      </p>
      {!compact && <p className="label">Available balance</p>}
    </article>
  );
}
