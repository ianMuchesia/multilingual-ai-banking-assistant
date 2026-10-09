import { config } from "../../config";
import type { Account } from "../../types/api";
import { formatKES, humanize, maskAccount, parseAmount } from "../../utils/format";
import type { SlotField } from "../../utils/slotFields";

interface CommonInputProps {
  id: string;
  disabled: boolean;
  required: boolean;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

interface Props {
  id: string;
  field: SlotField;
  value: string;
  required: boolean;
  missing: boolean;
  error?: string;
  accounts: Account[];
  disabled: boolean;
  onChange: (value: string) => void;
}

export function SlotFieldInput({ id, field, value, required, missing, error, accounts, disabled, onChange }: Props) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, field.kind === "amount" ? hintId : null].filter(Boolean).join(" ");
  const common: CommonInputProps = {
    id,
    disabled,
    required,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": describedBy || undefined,
  };

  return (
    <div className={`field${missing ? " field--missing" : ""}${error ? " field--error" : ""}`}>
      <label htmlFor={id} className="field__label">
        {field.label}
        {required && (
          <span className="field__req" aria-hidden="true">
            {" "}
            *
          </span>
        )}
        {missing && <span className="field__badge">Needed</span>}
      </label>

      {field.kind === "account" && (
        <select {...common} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select an account…</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.number}>
              {humanize(a.type)} {maskAccount(a.number)} — {formatKES(a.balance)}
            </option>
          ))}
          {value && !accounts.some((a) => a.number === value) && <option value={value}>{value}</option>}
        </select>
      )}

      {field.kind === "choice" && (
        <select {...common} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          {field.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}

      {field.kind === "text" && (
        <input
          {...common}
          className="input"
          type="text"
          value={value}
          placeholder={field.placeholder}
          autoComplete="off"
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {field.kind === "amount" && <AmountInput common={common} value={value} hintId={hintId} onChange={onChange} />}

      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}

interface AmountProps {
  common: CommonInputProps;
  value: string;
  hintId: string;
  onChange: (value: string) => void;
}

function AmountInput({ common, value, hintId, onChange }: AmountProps) {
  const parsed = parseAmount(value);
  return (
    <>
      <div className="amount-input">
        <span className="amount-input__ccy" aria-hidden="true">
          {config.currency}
        </span>
        <input
          {...common}
          className="amount-input__field"
          type="text"
          inputMode="decimal"
          value={value}
          placeholder="0.00"
          autoComplete="off"
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      <p id={hintId} className="field__hint">
        {Number.isFinite(parsed) && parsed > 0 ? formatKES(parsed) : "Enter an amount, e.g. 2,000 or 2k"}
      </p>
    </>
  );
}
