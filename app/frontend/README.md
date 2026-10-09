# Benki Yetu frontend

React 18 + TypeScript (strict) + Vite single-page app for **Benki Yetu**, a simulated Kenyan digital bank
with an AI chat assistant, **Benki AI**. Customers sign in, see balances and recent activity, and chat in
English, Kiswahili or Sheng. Every reply has a **"Why this answer?"** drawer that shows the intent
router's decision (route, intent, score, margin, top-3, nearest training examples, reasons, latency).
Money-moving requests open a secure review sheet; nothing is executed until the user presses Confirm.

> Demo only. The login page lists the seeded test users (`amina`, `brian`, `wanjiku`, password
> `password123`). Do not reuse this pattern with real credentials.

## Run in development (Windows cmd)

Requires Node.js 20.19+ or 22.12+ and the backend running on `http://localhost:8000`.

```cmd
cd app\frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `http://localhost:8000` (see `vite.config.ts`).
To point at another backend, create `app\frontend\.env.local` with:

```
VITE_DEV_API_TARGET=http://localhost:9000
```

## Build

```cmd
cd app\frontend
npm run build
npm run preview
```

`npm run build` type-checks (`tsc -b`) and writes static files to `dist\`.

## Docker

The image is a multi-stage build (Node build, then `nginx:alpine`) listening on port 80. nginx serves the
SPA with history fallback and proxies `/api/` to `http://backend:8000`, so it expects a compose service
named `backend` on the same network (see `app/docker-compose.yml`).

```cmd
cd app
docker compose up --build
```

Standalone (backend must be reachable as `backend` on the network you attach):

```cmd
cd app\frontend
docker build -t benki-yetu-frontend .
docker run --rm -p 8080:80 --network <your-network> benki-yetu-frontend
```

## Screens

| Route | Screen |
|---|---|
| `/login` | Split screen: brand panel + sign-in card with the demo-environment note |
| `/` | Home: total-balance hero (hide amounts), account cards, quick actions, recent transactions |
| `/assistant` | Benki AI chat: welcome state, example chips (en/sw/sheng), rich reply cards |

Accounts, Payments and Statements in the nav (and the quick actions) open Benki AI with a prefilled
message in the composer. Nothing is sent until the user presses Send.

## Source layout

```
src/
  api/          client.ts (fetch, auth header, errors, 401 -> logout), endpoints.ts, session.ts
  auth/         AuthProvider, useAuth, RequireAuth
  banking/      BankingProvider: accounts + chat state shared across screens, sheets, toasts
  components/   accounts, auth, brand, chat, confirm, debug, home, replies, shell, ui
  hooks/        useAccounts, useChat, useCountdown, useHealth
  pages/        LoginPage, HomePage, AssistantPage
  styles/       tokens.css (design tokens), global.css (components)
  theme/        theme mode (light default, manual toggle persisted)
  toast/        toast provider
  types/        api.ts (mirrors the API contract), chat.ts
  utils/        formatting, slot form definitions, selectors
  config.ts     the one place for API base, storage keys, routes, copy, example prompts
```

## Design tokens

All colours, fonts, spacing, radii and shadows live in **`src/styles/tokens.css`**. Components only use
`var(--role)` names.

- Colour roles and values (`--background`, `--surface`, `--border`, `--accent`, `--brand`, `--content`,
  `--content-muted`) are copied verbatim from `IanMuchesia/packages/theme/src/tokens.ts` (light and dark).
- Added for banking only: `--positive`, `--negative`, `--warning` (contrast-checked, documented in the file).
- Tints (`--surface-2`, `--accent-soft`, ...) are derived with `color-mix`, so changing a palette is an
  edit to the two palette blocks in `tokens.css` and nothing else.
- Theme: light by default (or the OS preference on first visit); the toggle in the top bar stores the choice
  in `localStorage` (`benki-yetu.theme`). An inline script in `index.html` applies it before first paint.
- Type: IBM Plex Sans 400/600 (UI), Plex Serif 400 + italic (reflective lines), Plex Mono 400/500 with
  tabular figures (amounts, account numbers, references, scores, labels). Loaded from Google Fonts.

## API contract (summary)

All endpoints are under `/api`, JSON, `Authorization: Bearer <token>` except login and health.

| Method | Path | Response |
|---|---|---|
| POST | `/auth/login` `{username, password}` | `{access_token, token_type: "bearer", user: {id, username, full_name}}` or 401 |
| GET | `/me` | `{id, username, full_name, accounts: Account[]}` |
| GET | `/accounts` | `Account[]` = `{id, number, type: "savings"\|"current", currency: "KES", balance}` |
| GET | `/transactions?account_id=&limit=10` | `Transaction[]` = `{id, reference, account_id, direction: "in"\|"out", amount, channel, counterparty, description, created_at, balance_after}` |
| GET | `/transactions/{reference}/receipt` | `{reference, amount, channel, counterparty, from_account, created_at, status}` |
| POST | `/chat` `{message}` | `{decision, reply, pending_action}` (below) |
| POST | `/actions/{id}/confirm` `{slots}` | `{status: "executed", transaction, receipt}`; 400/409 `{detail}`; 404 |
| POST | `/actions/{id}/cancel` | `{status: "cancelled"}` |
| GET | `/health` | `{status, router_mode}` |

- `decision`: `{intent, route: "direct"|"confirm"|"reject"|"llm", score, margin, top3: [intent, score][], nearest_examples: [text, intent, score][], reasons: string[], latency_ms}`
- `reply`: `{kind, text, data}` where `kind` is `balance` `{accounts}`, `mini_statement` `{transactions}`,
  `full_statement` `{start, end, transactions}`, `find_transaction` `{matches}`, `view_receipt`
  `{receipt|null, candidates}`, `transfer_help` `{topic, answer}`, or `confirm` / `reject` / `llm_pending` (`data: null`).
- `pending_action`: `null` or `{id, intent, slots, missing_slots, expires_at}`.
- Slots: `internal_transfer {from_account, to_account, amount}`; `external_transfer {from_account,
  destination_type: "bank"|"mobile", bank (required when "bank"), destination, amount}`; `lipa_na_mpesa
  {from_account, payment_type: "till"|"paybill", till_or_paybill, account_number (required for paybill), amount}`.
  `amount` is a JSON number in `pending_action.slots`; confirm accepts a number or numeric string.
- Errors: validation failures are `400 {detail: string}` (never 422); `404` = action missing or not the
  caller's; `409` = expired or not pending.
- `/health` `router_mode` is `"gemma"` or `"stub"`, shown as a subtle "Demo · stub router" chip in the top bar.

### Frontend assumptions

- `from_account` / `to_account` slot values are **account numbers** (strings). If the router returns an
  account id or a type (`"savings"`), the form maps it to the matching account number for display and
  sends the number on confirm.
- On confirm the frontend sends every slot for the intent; empty optional slots are sent as `null` and
  `amount` as a number.
- Ids for users, accounts and transactions are numbers; pending action ids are strings.
- A 401 from any authenticated call clears the session and returns to `/login`.
