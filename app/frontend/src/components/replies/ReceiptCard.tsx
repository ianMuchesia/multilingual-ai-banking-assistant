import { brand } from "../../config";
import type { Receipt } from "../../types/api";
import { formatDateTime, humanize } from "../../utils/format";
import { LogoMark } from "../brand/Logo";
import { Money } from "../ui/Money";

const SUCCESS_STATUSES = ["completed", "executed", "success", "successful"];

/** A transaction receipt styled like a printed slip. */
export function ReceiptCard({ receipt }: { receipt: Receipt }) {
  const ok = SUCCESS_STATUSES.includes(receipt.status.toLowerCase());
  return (
    <section className="receipt" aria-label={`Receipt ${receipt.reference}`}>
      <header className="receipt__head">
        <LogoMark size={22} />
        <span className="receipt__brand">{brand.name}</span>
        <span className={`status-tag${ok ? " status-tag--ok" : ""}`}>{humanize(receipt.status)}</span>
      </header>
      <p className="label receipt__caption">Amount</p>
      <p className="receipt__amount">
        <Money amount={receipt.amount} />
      </p>
      <dl className="receipt__lines">
        <div>
          <dt>To</dt>
          <dd>{receipt.counterparty}</dd>
        </div>
        <div>
          <dt>From</dt>
          <dd className="mono">{receipt.from_account}</dd>
        </div>
        <div>
          <dt>Channel</dt>
          <dd>{receipt.channel}</dd>
        </div>
        <div>
          <dt>Date</dt>
          <dd className="mono">{formatDateTime(receipt.created_at)}</dd>
        </div>
        <div>
          <dt>Reference</dt>
          <dd className="mono">{receipt.reference}</dd>
        </div>
      </dl>
      <p className="receipt__foot label">Asante for banking with {brand.name}</p>
    </section>
  );
}
