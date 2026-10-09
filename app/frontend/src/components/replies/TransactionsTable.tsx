import type { Transaction } from "../../types/api";
import { formatDateTime } from "../../utils/format";
import { Money } from "../ui/Money";

interface Props {
  transactions: Transaction[];
  caption: string;
  /** When given, each row gets a "Receipt" button. */
  onViewReceipt?: (reference: string) => void;
  activeReference?: string | null;
}

export function TransactionsTable({ transactions, caption, onViewReceipt, activeReference }: Props) {
  if (transactions.length === 0) return <p className="empty__line">Nothing matched. Try a different date or name.</p>;

  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={caption}>
      <table className="txn-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Details</th>
            <th scope="col" className="num">
              Amount
            </th>
            <th scope="col" className="num">
              Balance
            </th>
            {onViewReceipt && (
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {transactions.map((t) => (
            <tr key={t.id}>
              <td className="nowrap mono txn-table__date">{formatDateTime(t.created_at)}</td>
              <td>
                <span className="txn-table__who">{t.counterparty || t.description}</span>
                <span className="txn-table__meta">
                  <span className="chip-tag">{t.channel}</span> <span className="mono">{t.reference}</span>
                </span>
              </td>
              <td className="num nowrap">
                <Money amount={t.amount} sign={t.direction} className={t.direction === "in" ? "money--in" : undefined} />
              </td>
              <td className="num nowrap">
                <Money amount={t.balance_after} className="money--muted" />
              </td>
              {onViewReceipt && (
                <td>
                  <button
                    type="button"
                    className="link-btn"
                    aria-pressed={activeReference === t.reference}
                    onClick={() => onViewReceipt(t.reference)}
                  >
                    Receipt<span className="visually-hidden"> for {t.reference}</span>
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
