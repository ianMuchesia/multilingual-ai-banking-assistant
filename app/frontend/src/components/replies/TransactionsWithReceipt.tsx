import { useState } from "react";
import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import type { Receipt, Transaction } from "../../types/api";
import { InlineError } from "../ui/InlineError";
import { Skeleton } from "../ui/Skeleton";
import { ReceiptCard } from "./ReceiptCard";
import { TransactionsTable } from "./TransactionsTable";

interface Props {
  transactions: Transaction[];
  caption: string;
}

/** Transactions table whose rows can open their receipt inline (GET /transactions/{ref}/receipt). */
export function TransactionsWithReceipt({ transactions, caption }: Props) {
  const [active, setActive] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = async (reference: string) => {
    if (active === reference) {
      setActive(null);
      setReceipt(null);
      return;
    }
    setActive(reference);
    setReceipt(null);
    setError(null);
    setLoading(true);
    try {
      setReceipt(await api.receipt(reference));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not load receipt.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="stack">
      <TransactionsTable
        transactions={transactions}
        caption={caption}
        activeReference={active}
        onViewReceipt={(ref) => void open(ref)}
      />
      <div aria-live="polite">
        {loading && <Skeleton height="180px" radius="12px" />}
        {error && <InlineError message={error} />}
        {receipt && <ReceiptCard receipt={receipt} />}
      </div>
    </div>
  );
}
