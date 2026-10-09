import { LockKeyhole, ShieldCheck } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import { useCountdown } from "../../hooks/useCountdown";
import type { Account, ConfirmResponse, PendingAction } from "../../types/api";
import { humanize } from "../../utils/format";
import {
  fieldsFor,
  initialValues,
  isRequired,
  isVisible,
  toSlots,
  validate,
  type FormValues,
} from "../../utils/slotFields";
import { InlineError } from "../ui/InlineError";
import { Countdown } from "./Countdown";
import { SlotFieldInput } from "./SlotFieldInput";

interface Props {
  titleId: string;
  action: PendingAction;
  accounts: Account[];
  onExecuted: (result: ConfirmResponse) => void;
  onCancelled: () => void;
}

type Busy = "confirm" | "cancel" | null;

function errorMessage(e: unknown): string {
  if (!(e instanceof ApiError)) return "Something went wrong. Please try again.";
  if (e.status === 404) return "This request no longer exists. Please ask again.";
  return e.detail;
}

/** Editable review of a pending money-moving action. Nothing is sent until Confirm. */
export function ReviewForm({ titleId, action, accounts, onExecuted, onCancelled }: Props) {
  const fields = useMemo(
    () => fieldsFor(action.intent, action.slots, action.missing_slots),
    [action.intent, action.slots, action.missing_slots],
  );
  const [values, setValues] = useState<FormValues>(() => initialValues(fields, action.slots, accounts));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [attempted, setAttempted] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const remaining = useCountdown(action.expires_at);
  const expired = remaining <= 0;

  const setField = (name: string, value: string) => {
    const next = { ...values, [name]: value };
    setValues(next);
    if (attempted) setErrors(validate(fields, next, action.missing_slots));
  };

  const handleConfirm = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setAttempted(true);
    setServerError(null);
    const found = validate(fields, values, action.missing_slots);
    setErrors(found);
    if (Object.keys(found).length > 0 || expired) return;

    setBusy("confirm");
    try {
      onExecuted(await api.confirmAction(action.id, toSlots(fields, values)));
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const handleCancel = async () => {
    setServerError(null);
    setBusy("cancel");
    try {
      await api.cancelAction(action.id);
      onCancelled();
    } catch (err) {
      // Already expired or gone on the server: nothing can execute, so treat as cancelled.
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) onCancelled();
      else setServerError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const missingCount = action.missing_slots.filter((n) => !(values[n] ?? "").trim()).length;

  return (
    <div className="review">
      <header className="review__head">
        <span className="review__lock" aria-hidden="true">
          <LockKeyhole size={20} />
        </span>
        <div>
          <p className="label">{humanize(action.intent)}</p>
          <h2 id={titleId} className="sheet__title">
            Review and confirm
          </h2>
        </div>
        <Countdown seconds={remaining} />
      </header>

      <p className="review__note">
        <ShieldCheck size={16} aria-hidden="true" />
        Nothing is sent until you press Confirm.
        {missingCount > 0 && ` ${missingCount} detail${missingCount === 1 ? "" : "s"} still needed.`}
      </p>

      <form className="review__form" onSubmit={(e) => void handleConfirm(e)} noValidate>
        {fields
          .filter((f) => isVisible(f, values))
          .map((f) => (
            <SlotFieldInput
              key={f.name}
              id={`${titleId}-${f.name}`}
              field={f}
              value={values[f.name] ?? ""}
              required={isRequired(f, values, action.missing_slots)}
              missing={action.missing_slots.includes(f.name) && !(values[f.name] ?? "").trim()}
              error={errors[f.name]}
              accounts={accounts}
              disabled={busy !== null || expired}
              onChange={(v) => setField(f.name, v)}
            />
          ))}

        {serverError && <InlineError message={serverError} />}
        {expired && !serverError && (
          <InlineError message="This request has expired. Send your message again to start over." />
        )}

        <div className="review__actions">
          <button
            type="button"
            className="btn btn--outline"
            disabled={busy !== null}
            onClick={() => void handleCancel()}
          >
            {busy === "cancel" ? "Cancelling…" : "Cancel"}
          </button>
          <button type="submit" className="btn btn--primary" disabled={busy !== null || expired}>
            <LockKeyhole size={16} aria-hidden="true" />
            {busy === "confirm" ? "Confirming…" : "Confirm"}
          </button>
        </div>
      </form>
    </div>
  );
}
