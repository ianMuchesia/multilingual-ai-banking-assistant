import { config } from "../../config";
import { formatAmount } from "../../utils/format";

interface Props {
  amount: number;
  /** Prefix a sign: "+" for money in, "−" for money out. */
  sign?: "in" | "out";
  hidden?: boolean;
  className?: string;
}

/** Amount in Plex Mono with tabular figures, e.g. "KES 2,000.00". */
export function Money({ amount, sign, hidden = false, className = "" }: Props) {
  const prefix = sign === "in" ? "+" : sign === "out" ? "−" : "";
  return (
    <span className={`money ${className}`}>
      <span className="money__ccy">{config.currency}</span>{" "}
      {hidden ? (
        <>
          <span aria-hidden="true">••••••</span>
          <span className="visually-hidden">hidden</span>
        </>
      ) : (
        `${prefix}${formatAmount(amount)}`
      )}
    </span>
  );
}
