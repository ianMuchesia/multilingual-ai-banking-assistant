// Single place for runtime configuration and product copy constants.
// The API is always reached via a same-origin relative path: the Vite dev server
// proxies it in development and nginx proxies it in the Docker image.

export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  sessionStorageKey: "benki-yetu.auth",
  /** Must match the key read by the theme init script in index.html. */
  themeStorageKey: "benki-yetu.theme",
  currency: "KES",
  locale: "en-KE",
  transactionsLimit: 10,
  recentLimit: 6,
  toastMs: 4500,
} as const;

export const routes = {
  login: "/login",
  home: "/",
  assistant: "/assistant",
} as const;

export const brand = {
  name: "Benki Yetu",
  assistant: "Benki AI",
  tagline: "Banking that understands you, in English, Kiswahili and Sheng.",
} as const;

/** Dev seed users shown on the login page (demo environment only). */
export const demoUsers = [
  { username: "amina", password: "password123" },
  { username: "brian", password: "password123" },
  { username: "wanjiku", password: "password123" },
] as const;

export type Lang = "en" | "sw" | "sheng";

/** Example chat messages shown as clickable chips. */
export const exampleMessages: { lang: Lang; text: string }[] = [
  { lang: "en", text: "What is my balance?" },
  { lang: "en", text: "Show my last 5 transactions" },
  { lang: "en", text: "Send 1500 from savings to current" },
  { lang: "sw", text: "salio langu ni ngapi" },
  { lang: "sw", text: "nionyeshe taarifa ya mwezi uliopita" },
  { lang: "sw", text: "nitumie risiti ya muamala wa jana" },
  { lang: "sheng", text: "tuma 2k kwa KCB yangu" },
  { lang: "sheng", text: "lipa till 123456 500" },
  { lang: "sheng", text: "niaje, nikopeshe 50k" },
];

/** Prefilled prompts used by quick actions and the non-home nav items. Nothing is sent automatically. */
export const prompts = {
  balances: "Show my account balances",
  send: "Send money to my KCB account",
  payBill: "Pay till 123456 KES 500",
  statement: "Show my statement for last month",
  receipts: "Show me the receipt for my last transaction",
  recent: "Show my last 10 transactions",
} as const;
