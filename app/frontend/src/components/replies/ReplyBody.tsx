import type { Reply } from "../../types/api";
import { formatDate } from "../../utils/format";
import { BalanceReply } from "./BalanceReply";
import { FaqReply } from "./FaqReply";
import { Notice } from "./Notice";
import { ReceiptCard } from "./ReceiptCard";
import { TransactionsWithReceipt } from "./TransactionsWithReceipt";

/** Renders the structured part of an assistant reply, by kind. The reply text is rendered by the caller. */
export function ReplyBody({ reply }: { reply: Reply }) {
  switch (reply.kind) {
    case "balance":
      return reply.data ? <BalanceReply data={reply.data} /> : null;

    case "mini_statement":
      return reply.data ? (
        <TransactionsWithReceipt transactions={reply.data.transactions} caption="Mini statement" />
      ) : null;

    case "full_statement":
      return reply.data ? (
        <div className="stack">
          <p className="label">
            {formatDate(reply.data.start)} – {formatDate(reply.data.end)} · {reply.data.transactions.length}{" "}
            transactions
          </p>
          <TransactionsWithReceipt transactions={reply.data.transactions} caption="Full statement" />
        </div>
      ) : null;

    case "find_transaction":
      return reply.data ? (
        <TransactionsWithReceipt transactions={reply.data.matches} caption="Matching transactions" />
      ) : null;

    case "view_receipt":
      if (!reply.data) return null;
      if (reply.data.receipt) return <ReceiptCard receipt={reply.data.receipt} />;
      return reply.data.candidates.length > 0 ? (
        <div className="stack">
          <p className="label">Pick a transaction to see its receipt</p>
          <TransactionsWithReceipt transactions={reply.data.candidates} caption="Receipt candidates" />
        </div>
      ) : null;

    case "transfer_help":
      return reply.data ? <FaqReply data={reply.data} /> : null;

    case "reject":
      return (
        <Notice tone="reject" title="Not something I can do yet">
          I can help with balances, statements, receipts, transfers and Lipa na M-Pesa.
        </Notice>
      );

    case "llm_pending":
      return (
        <Notice tone="rephrase" title="Not sure I understood">
          Could you rephrase? For example: “salio langu ni ngapi” or “tuma 2k kwa KCB yangu”.
        </Notice>
      );

    case "confirm":
      return null;
  }
}
