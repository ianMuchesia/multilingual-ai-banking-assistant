import { SendHorizontal } from "lucide-react";
import { useEffect, useId, useRef, type FormEvent, type KeyboardEvent } from "react";

interface Props {
  value: string;
  onChange: (text: string) => void;
  onSend: (text: string) => void;
  disabled: boolean;
}

/** Message box. Controlled from outside so quick actions can prefill it. */
export function Composer({ value, onChange, onSend, disabled }: Props) {
  const inputId = useId();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // A prefilled draft (from a quick action or nav item) gets focus so the user can
  // review it and press Enter. While typing, the box already has focus, so this is a no-op.
  useEffect(() => {
    const el = inputRef.current;
    if (value && el && document.activeElement !== el) {
      el.focus();
      el.setSelectionRange(value.length, value.length);
    }
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    onChange("");
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    submit();
  };

  // Enter sends, Shift+Enter inserts a newline.
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <label htmlFor={inputId} className="visually-hidden">
        Message Benki AI
      </label>
      <textarea
        ref={inputRef}
        id={inputId}
        className="composer__input"
        rows={1}
        value={value}
        placeholder="Ask in English, Kiswahili or Sheng…"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        maxLength={500}
      />
      <button type="submit" className="composer__send" disabled={disabled || !value.trim()} aria-label="Send message">
        <SendHorizontal size={18} aria-hidden="true" />
      </button>
    </form>
  );
}
