import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

interface Props {
  open: boolean;
  onClose: () => void;
  /** id of the element that names the dialog */
  labelledBy: string;
  /** "drawer": right side panel on desktop. "modal": centred dialog on desktop. Both are bottom sheets on phones. */
  variant: "drawer" | "modal";
  className?: string;
  children: ReactNode;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Accessible modal surface: focus moves in and is trapped, Escape closes, focus returns on close. */
export function Sheet({ open, onClose, labelledBy, variant, className = "", children }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel)?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onCloseRef.current();
      return;
    }
    if (e.key !== "Tab" || !panelRef.current) return;
    const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (items.length === 0) return;
    const firstItem = items[0];
    const lastItem = items[items.length - 1];
    if (e.shiftKey && document.activeElement === firstItem) {
      e.preventDefault();
      lastItem.focus();
    } else if (!e.shiftKey && document.activeElement === lastItem) {
      e.preventDefault();
      firstItem.focus();
    }
  };

  return createPortal(
    <div className={`sheet-root sheet-root--${variant}`} onKeyDown={handleKeyDown}>
      <div className="sheet-scrim" onClick={() => onCloseRef.current()} aria-hidden="true" />
      <div
        ref={panelRef}
        className={`sheet sheet--${variant} ${className}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
      >
        <span className="sheet__grabber" aria-hidden="true" />
        <button type="button" className="icon-btn sheet__close" onClick={() => onCloseRef.current()}>
          <X size={18} aria-hidden="true" />
          <span className="visually-hidden">Close</span>
        </button>
        {children}
      </div>
    </div>,
    document.body,
  );
}
