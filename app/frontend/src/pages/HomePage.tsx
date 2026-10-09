import { Sparkles } from "lucide-react";
import { useBanking } from "../banking/bankingContext";
import { useAuth } from "../auth/authContext";
import { AccountCard } from "../components/accounts/AccountCard";
import { BalanceHero } from "../components/home/BalanceHero";
import { QuickActions } from "../components/home/QuickActions";
import { RecentTransactions } from "../components/home/RecentTransactions";
import { InlineError } from "../components/ui/InlineError";
import { Skeleton } from "../components/ui/Skeleton";
import { brand, prompts } from "../config";

export function HomePage() {
  const { session } = useAuth();
  const { accounts: state, hideAmounts, toggleHideAmounts, openAssistant } = useBanking();
  const { accounts, recent, loading, loaded, error, refresh } = state;
  const firstName = session?.user.full_name.split(" ")[0] ?? "";

  return (
    <div className="page">
      <header className="page__header">
        <p className="label">Home</p>
        <h1 className="page__title">Karibu tena, {firstName}</h1>
      </header>

      {error && <InlineError message={error} onRetry={() => void refresh()} />}

      <div className="home-grid">
        <div className="home-grid__main">
          <BalanceHero
            accounts={accounts}
            loading={loading}
            loaded={loaded}
            hidden={hideAmounts}
            onToggleHidden={toggleHideAmounts}
            onRefresh={() => void refresh()}
          />

          <section aria-labelledby="accounts-title">
            <h2 id="accounts-title" className="section-title">
              Your accounts
            </h2>
            <div className="account-grid">
              {loaded
                ? accounts.map((a) => <AccountCard key={a.id} account={a} hidden={hideAmounts} />)
                : [0, 1].map((i) => (
                    <div key={i} className="account-card" aria-hidden="true">
                      <Skeleton width="40%" />
                      <Skeleton width="70%" height="28px" />
                      <Skeleton width="30%" height="12px" />
                    </div>
                  ))}
            </div>
          </section>

          <QuickActions onPick={openAssistant} />
        </div>

        <div className="home-grid__side">
          <RecentTransactions
            transactions={recent}
            loaded={loaded}
            hidden={hideAmounts}
            onSeeAll={() => openAssistant(prompts.recent)}
          />

          <button type="button" className="ai-promo" onClick={() => openAssistant()}>
            <span className="ai-avatar" aria-hidden="true">
              <Sparkles size={18} />
            </span>
            <span>
              <span className="ai-promo__title">Ask {brand.assistant}</span>
              <span className="ai-promo__line">“salio langu ni ngapi?” works too.</span>
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
