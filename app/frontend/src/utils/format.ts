import { config } from "../config";

const amountFormatter = new Intl.NumberFormat(config.locale, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateTimeFormatter = new Intl.DateTimeFormat(config.locale, {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat(config.locale, {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

/** "2,000.00" */
export function formatAmount(amount: number): string {
  return amountFormatter.format(amount);
}

/** "KES 2,000.00" */
export function formatKES(amount: number): string {
  return `${config.currency} ${formatAmount(amount)}`;
}

function toDate(iso: string): Date | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(iso: string): string {
  const d = toDate(iso);
  return d ? dateTimeFormatter.format(d) : iso;
}

export function formatDate(iso: string): string {
  const d = toDate(iso);
  return d ? dateFormatter.format(d) : iso;
}

const relativeFormatter = new Intl.RelativeTimeFormat(config.locale, { numeric: "auto" });

/** "Today, 14:05", "Yesterday", "3 days ago", or a date for anything older than a week. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const d = toDate(iso);
  if (!d) return iso;
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(d) - startOf(now)) / 86_400_000);
  if (days === 0) {
    const time = d.toLocaleTimeString(config.locale, { hour: "2-digit", minute: "2-digit" });
    return `Today, ${time}`;
  }
  if (days >= -6 && days < 0) return relativeFormatter.format(days, "day");
  return formatDate(iso);
}

/** Show only the last 4 digits of an account number. */
export function maskAccount(number: string): string {
  return number.length > 4 ? `•••• ${number.slice(-4)}` : number;
}

/** 0.8734 -> "0.873" */
export function formatScore(score: number): string {
  return score.toFixed(3);
}

/** "internal_transfer" -> "Internal transfer" */
export function humanize(identifier: string): string {
  const spaced = identifier.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Parse a user-typed amount such as "2,000" or "2k" into a number (NaN if invalid). */
export function parseAmount(input: string): number {
  const cleaned = input.replace(/[,\s]/g, "").replace(/^kes/i, "").toLowerCase();
  if (cleaned === "") return Number.NaN;
  const match = /^(\d+(?:\.\d+)?)(k|m)?$/.exec(cleaned);
  if (!match) return Number.NaN;
  const base = Number(match[1]);
  const multiplier = match[2] === "k" ? 1_000 : match[2] === "m" ? 1_000_000 : 1;
  return base * multiplier;
}
