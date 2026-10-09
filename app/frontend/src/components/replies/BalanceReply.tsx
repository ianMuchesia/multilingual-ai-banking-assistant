import type { BalanceData } from "../../types/api";
import { AccountCard } from "../accounts/AccountCard";

export function BalanceReply({ data }: { data: BalanceData }) {
  return (
    <div className="balance-grid">
      {data.accounts.map((a) => (
        <AccountCard key={a.id} account={a} compact />
      ))}
    </div>
  );
}
