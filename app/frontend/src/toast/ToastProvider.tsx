import { CircleCheck, CircleX, Info, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { config } from "../config";
import { ToastContext, type Toast, type ToastContextValue, type ToastTone } from "./toastContext";

const ICONS = { success: CircleCheck, error: CircleX, info: Info } as const;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (tone: ToastTone, message: string) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev.slice(-2), { id, tone, message }]);
      window.setTimeout(() => dismiss(id), config.toastMs);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toaster" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.tone];
          return (
            <div key={t.id} className={`toast toast--${t.tone}`}>
              <Icon size={18} aria-hidden="true" />
              <p className="toast__msg">{t.message}</p>
              <button type="button" className="icon-btn icon-btn--sm" onClick={() => dismiss(t.id)}>
                <X size={16} aria-hidden="true" />
                <span className="visually-hidden">Dismiss</span>
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
