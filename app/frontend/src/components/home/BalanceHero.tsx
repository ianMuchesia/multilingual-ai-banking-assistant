import { Eye, EyeOff, RefreshCw } from "lucide-react";
import type { Account } from "../../types/api";
import { Money } from "../ui/Money";
import { Skeleton } from "../ui/Skeleton";

interface Props {
  accounts: Account[];
  loading: boolean;
  loaded: boolean;
  hidden: boolean;
  onToggleHidden: () => void;
  onRefresh: () => void;
}

export function BalanceHero({ accounts, loading, loaded, hidden, onToggleHidden, onRefresh }: Props) {
  const total = accounts.reduce((sum, a) => sum + a.balance, 0);

  return (
    <section className="hero" aria-labelledby="hero-title">
      <span className="hero__band" aria-hidden="true" />
      <div className="hero__top">
        <h2 id="hero-title" className="label hero__label">
          Total balance
        </h2>
        <div className="hero__actions">
          <button
            type="button"
            className="icon-btn icon-btn--on-hero"
            onClick={onRefresh}
            disabled={loading}
            aria-label="Refresh balances"
          >
            <RefreshCw size={16} aria-hidden="true" className={loading ? "spin" : undefined} />
          </button>
          <button
            type="button"
            className="icon-btn icon-btn--on-hero"
            onClick={onToggleHidden}
            aria-pressed={hidden}
            aria-label={hidden ? "Show amounts" : "Hide amounts"}
          >
            {hidden ? <Eye size={16} aria-hidden="true" /> : <EyeOff size={16} aria-hidden="true" />}
          </button>
        </div>
      </div>
      <p className="hero__amount">
        {loaded ? <Money amount={total} hidden={hidden} /> : <Skeleton width="60%" height="40px" className="skeleton--on-hero" />}
      </p>
      <p className="hero__meta label">
        {loaded ? `Across ${accounts.length} account${accounts.length === 1 ? "" : "s"}` : "Loading accounts…"}
      </p>
    </section>
  );
}
