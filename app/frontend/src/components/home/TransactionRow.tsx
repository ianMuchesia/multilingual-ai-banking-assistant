import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { Transaction } from "../../types/api";
import { formatRelative } from "../../utils/format";
import { Money } from "../ui/Money";

export function TransactionRow({ txn, hidden = false }: { txn: Transaction; hidden?: boolean }) {
  const incoming = txn.direction === "in";
  const Arrow = incoming ? ArrowDownLeft : ArrowUpRight;

  return (
    <li className="txn-row">
      <span className={`txn-row__icon${incoming ? " txn-row__icon--in" : ""}`} aria-hidden="true">
        <Arrow size={16} />
      </span>
      <div className="txn-row__main">
        <p className="txn-row__who">{txn.counterparty || txn.description}</p>
        <p className="txn-row__meta">
          <span className="chip-tag">{txn.channel}</span>
          <span className="label">{formatRelative(txn.created_at)}</span>
        </p>
      </div>
      <span className="visually-hidden">{incoming ? "Money in" : "Money out"}</span>
      <Money
        amount={txn.amount}
        sign={txn.direction}
        hidden={hidden}
        className={incoming ? "money--in" : undefined}
      />
    </li>
  );
}
