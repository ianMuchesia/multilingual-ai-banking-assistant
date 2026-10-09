// Form field definitions for each money-moving intent's slots.
import type { Account, ActionIntent, Slots } from "../types/api";
import { humanize, parseAmount } from "./format";

export type FieldKind = "account" | "amount" | "text" | "choice";

export interface SlotField {
  name: string;
  label: string;
  kind: FieldKind;
  options?: { value: string; label: string }[];
  placeholder?: string;
  /** Required regardless of missing_slots; may depend on the other values. */
  required: (values: FormValues) => boolean;
  /** Hidden when false (e.g. account_number only for paybill). */
  visible?: (values: FormValues) => boolean;
}

/** Form values are kept as strings while editing. */
export type FormValues = Record<string, string>;

const always = () => true;

const FIELDS: Record<ActionIntent, SlotField[]> = {
  internal_transfer: [
    { name: "from_account", label: "From account", kind: "account", required: always },
    { name: "to_account", label: "To account", kind: "account", required: always },
    { name: "amount", label: "Amount", kind: "amount", required: always },
  ],
  external_transfer: [
    { name: "from_account", label: "From account", kind: "account", required: always },
    {
      name: "destination_type",
      label: "Send to",
      kind: "choice",
      options: [
        { value: "bank", label: "Another bank" },
        { value: "mobile", label: "Mobile money (M-Pesa, Airtel Money)" },
      ],
      required: always,
    },
    {
      name: "bank",
      label: "Bank name",
      kind: "text",
      placeholder: "e.g. KCB",
      required: (v) => v.destination_type === "bank",
      visible: (v) => v.destination_type === "bank",
    },
    {
      name: "destination",
      label: "Account or phone number",
      kind: "text",
      placeholder: "e.g. 1234567890 or 0712 345 678",
      required: always,
    },
    { name: "amount", label: "Amount", kind: "amount", required: always },
  ],
  lipa_na_mpesa: [
    { name: "from_account", label: "From account", kind: "account", required: always },
    {
      name: "payment_type",
      label: "Payment type",
      kind: "choice",
      options: [
        { value: "till", label: "Buy Goods (Till)" },
        { value: "paybill", label: "Paybill" },
      ],
      required: always,
    },
    {
      name: "till_or_paybill",
      label: "Till / Paybill number",
      kind: "text",
      placeholder: "e.g. 123456",
      required: always,
    },
    {
      name: "account_number",
      label: "Paybill account number",
      kind: "text",
      required: (v) => v.payment_type === "paybill",
      visible: (v) => v.payment_type === "paybill",
    },
    { name: "amount", label: "Amount", kind: "amount", required: always },
  ],
};

function isActionIntent(intent: string): intent is ActionIntent {
  return intent in FIELDS;
}

/** Fields for an intent; unknown intents fall back to plain text fields for every slot. */
export function fieldsFor(intent: string, slots: Slots, missing: string[]): SlotField[] {
  if (isActionIntent(intent)) return FIELDS[intent];
  const names = Array.from(new Set([...Object.keys(slots), ...missing]));
  return names.map((name): SlotField => ({
    name,
    label: humanize(name),
    kind: name === "amount" ? "amount" : name === "from_account" || name === "to_account" ? "account" : "text",
    required: () => missing.includes(name),
  }));
}

export function toFormValues(slots: Slots): FormValues {
  const values: FormValues = {};
  for (const [key, value] of Object.entries(slots)) {
    values[key] = value === null || value === undefined ? "" : String(value);
  }
  return values;
}

/**
 * Initial form values. Account slots are normalised to an account number so the
 * select can show them, accepting a number, an id or a type ("savings") from the router.
 */
export function initialValues(fields: SlotField[], slots: Slots, accounts: Account[]): FormValues {
  const values = toFormValues(slots);
  for (const field of fields) {
    const raw = values[field.name] ?? "";
    if (field.kind === "account" && raw) {
      const match = accounts.find(
        (a) => a.number === raw || String(a.id) === raw || a.type === raw.toLowerCase(),
      );
      values[field.name] = match ? match.number : raw;
    } else {
      values[field.name] = raw;
    }
  }
  return values;
}

export function isVisible(field: SlotField, values: FormValues): boolean {
  return field.visible ? field.visible(values) : true;
}

export function isRequired(field: SlotField, values: FormValues, missing: string[]): boolean {
  return isVisible(field, values) && (field.required(values) || missing.includes(field.name));
}

/** Returns field name -> error message for every invalid field. */
export function validate(fields: SlotField[], values: FormValues, missing: string[]): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (!isVisible(field, values)) continue;
    const value = (values[field.name] ?? "").trim();
    if (!value) {
      if (isRequired(field, values, missing)) errors[field.name] = `${field.label} is required.`;
      continue;
    }
    if (field.kind === "amount") {
      const amount = parseAmount(value);
      if (!Number.isFinite(amount) || amount <= 0) errors[field.name] = "Enter an amount greater than 0.";
    }
  }
  if (values.from_account && values.to_account && values.from_account === values.to_account) {
    errors.to_account = "Choose a different account from the source account.";
  }
  return errors;
}

/** Converts form values back to slots for the confirm request. */
export function toSlots(fields: SlotField[], values: FormValues): Slots {
  const slots: Slots = {};
  for (const field of fields) {
    const value = (values[field.name] ?? "").trim();
    if (!isVisible(field, values) || value === "") {
      slots[field.name] = null;
    } else if (field.kind === "amount") {
      slots[field.name] = parseAmount(value);
    } else {
      slots[field.name] = value;
    }
  }
  return slots;
}
