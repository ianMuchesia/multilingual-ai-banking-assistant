import { ScrollText } from "lucide-react";
import type { Transaction } from "../../types/api";
import { EmptyState } from "../ui/EmptyState";
import { Skeleton } from "../ui/Skeleton";
import { TransactionRow } from "./TransactionRow";

interface Props {
  transactions: Transaction[];
  loaded: boolean;
  hidden: boolean;
  onSeeAll: () => void;
}

export function RecentTransactions({ transactions, loaded, hidden, onSeeAll }: Props) {
  return (
    <section className="card" aria-labelledby="recent-title">
      <div className="card__head">
        <h2 id="recent-title" className="section-title">
          Recent transactions
        </h2>
        <button type="button" className="link-btn" onClick={onSeeAll}>
          Ask Benki AI for more
        </button>
      </div>

      {!loaded ? (
        <ul className="txn-list" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className="txn-row">
              <Skeleton width="36px" height="36px" radius="50%" />
              <div className="txn-row__main">
                <Skeleton width="50%" />
                <Skeleton width="30%" height="12px" />
              </div>
              <Skeleton width="80px" />
            </li>
          ))}
        </ul>
      ) : transactions.length === 0 ? (
        <EmptyState icon={ScrollText} line="Quiet so far. Your transactions will gather here." />
      ) : (
        <ul className="txn-list">
          {transactions.map((t) => (
            <TransactionRow key={t.id} txn={t} hidden={hidden} />
          ))}
        </ul>
      )}
    </section>
  );
}
