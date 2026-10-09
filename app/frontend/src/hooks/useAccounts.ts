import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import { config } from "../config";
import type { Account, Transaction } from "../types/api";

export interface AccountsState {
  accounts: Account[];
  recent: Transaction[];
  loading: boolean;
  /** True once the first load finished (success or error); drives skeletons. */
  loaded: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useAccounts(): AccountsState {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [recent, setRecent] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [accs, txns] = await Promise.all([api.accounts(), api.transactions(undefined, config.recentLimit)]);
      setAccounts(accs);
      setRecent(txns);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not load accounts.");
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { accounts, recent, loading, loaded, error, refresh };
}
