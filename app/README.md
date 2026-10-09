# Benki Yetu chat banking (simulation)

A full-stack simulation of a banking chat assistant for the fictional bank **Benki Yetu**.
The customer types a message; the **intent router** (`../intent-router`) decides what kind of
request it is; the backend answers read-only requests directly and turns money-moving requests
into a **pending action** that the customer must explicitly confirm.

Everything here is demo data. No real customers, accounts, limits or charges.

## Architecture

```
 Browser ──► http://localhost:3000
              │
   ┌──────────▼───────────┐
   │ frontend (nginx :80) │  React app; /api/* proxied to backend:8000
   └──────────┬───────────┘
              │ /api (JSON, Bearer JWT)
   ┌──────────▼──────────────────────────────────────────────────────────┐
   │ backend (FastAPI :8000)                                             │
   │                                                                     │
   │  api/ (thin routes) ──► services/ ──► db/ (SQLAlchemy) ─────────────┼──► db (PostgreSQL 16)
   │                            │                                        │     users, accounts,
   │   POST /api/chat ──────────┤                                        │     transactions,
   │     router_client ◄────────┘  ROUTER_MODE=gemma: intent-router      │     pending_actions,
   │       │                          Router (EmbeddingGemma, CPU)       │     router_audit
   │       │                        ROUTER_MODE=stub: keyword rules      │
   │       ▼                                                             │
   │     route: direct  ─► view/info reply (balance, statements, ...)    │
   │            confirm ─► slots/ (regex) ─► pending_action (5 min)      │
   │            reject  ─► polite decline                                │
   │            llm     ─► "llm_pending" (LLM step not built yet)        │
   │                                                                     │
   │   POST /api/actions/{id}/confirm ─► services/actions.py  ◄── the ONLY│
   │                                       place money moves             │
   └─────────────────────────────────────────────────────────────────────┘
              ▲ read-only bind mount
   %USERPROFILE%\.cache\huggingface  (EmbeddingGemma weights, ~1.5 GB)
```

Backend layout (`backend/bankchat/`):

| Folder / file | What it does |
|---|---|
| `settings.py` | every setting, from env / `app\.env` |
| `api/` | thin FastAPI routes, dependencies, error mapping |
| `services/` | the logic: chat, view replies, actions (confirm/cancel), auth, FAQ, audit |
| `slots/` | rule-based slot extraction: amounts, phones, account/till/paybill numbers, banks, dates |
| `router_client/` | one `RouterClient` interface; `gemma.py` (real router), `stub.py` (keywords) |
| `db/` | models, session, idempotent seed (`seed.py`, `seed_data.py`, `seed_generator.py`) |
| `data/transfer_faq.json` | transfer_help answers (DEMO limits/charges/timings) |

## Run it (Windows cmd)

Prerequisites: Docker Desktop; the EmbeddingGemma weights in your Hugging Face cache
(run `python -m scripts.sanity_check --backend gemma` once in `intent-router` if they aren't);
`intent-router\cache\gemma_768.npz` built (`python -m scripts.build_index --backend gemma`).

```bat
cd C:\Users\<you>\Desktop\projects\BankingAgents\app
copy .env.example .env
notepad .env
rem set HF_CACHE_DIR=C:\Users\<you>\.cache\huggingface and a JWT_SECRET
docker compose up --build
```

Open http://localhost:3000. API docs: http://localhost:8000/docs. Health: http://localhost:8000/api/health.

The first start takes a while (image build; the model loads in ~10-20 s). The backend seeds the
database on start; it does nothing if the data is already there. Reset everything with
`docker compose down -v`.

Without the model (no HF cache, small image): set `ROUTER_MODE=stub` and `INSTALL_GEMMA=false` in `.env`.
`HF_CACHE_DIR` must still point at an existing folder (any empty folder works).

### Backend tests

```bat
cd C:\Users\<you>\Desktop\projects\BankingAgents\app\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest
```

Tests use in-memory SQLite and the stub router; no Docker, no model.

### Backend without Docker

Postgres from compose, backend on the host:

```bat
cd C:\Users\<you>\Desktop\projects\BankingAgents\app
docker compose up -d db
cd backend
.venv\Scripts\activate
set ROUTER_MODE=stub
python -m bankchat.db.seed
uvicorn bankchat.main:app --reload --port 8000
```

With the real router, install the model dependencies once (CPU torch), then:

```bat
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -r requirements-gemma.txt
set ROUTER_MODE=gemma
uvicorn bankchat.main:app --port 8000
```

`DATABASE_URL`, `JWT_SECRET` etc. are read from `app\.env`; `set` variables override it.
Use `python -m bankchat.db.seed --reset` to drop and re-create the demo data.

## Test users (DEV ONLY)

| Username | Password | Profile |
|---|---|---|
| `amina` | `password123` | salaried, savings + current |
| `brian` | `password123` | salaried, savings + current |
| `wanjiku` | `password123` | salaried, savings + current |

Each has ~6 months of deterministic history: salary, rent and utility paybills, till payments,
M-Pesa in/out, PesaLink, internal transfers. `grace`, `kevin` and `fatuma` are other Benki Yetu
customers who receive internal transfers ("send 2000 to grace"); they cannot log in.
Account numbers: savings `11` + 10 digits, current `12` + 10 digits (amina: `110000000001` / `120000000001`).

The password is a shared, published dev value. Never use this seed on a real database.

## ROUTER_MODE

| Mode | What runs | Use for |
|---|---|---|
| `gemma` | intent-router's `Router` (EmbeddingGemma on CPU), loaded once at startup, offline | the real thing |
| `stub` | `router_client/stub.py`: keyword rules with the same output shape and policy | frontend dev, CI, tests |

Both implement `RouterClient.route(text) -> RouterDecision`. The response's `decision` shows
intent, route, score, margin, top 3, nearest examples and reasons, so the UI can explain itself.
`intent-router` is used read-only; if its `train.json` changes, rebuild its index or the router
refuses to start.

## Safety design

- **`/api/chat` never moves money.** For an action intent (`internal_transfer`, `external_transfer`,
  `lipa_na_mpesa`) it only stores a `pending_action` with the extracted slots and the missing ones.
- **Money moves only in `POST /api/actions/{id}/confirm`** (`services/actions.py`), in one database
  transaction, with the action and the accounts locked (`SELECT ... FOR UPDATE`, accounts in id order).
  It checks, in order: the action belongs to the caller (else 404, same as "doesn't exist"), it is
  `pending` and not expired (5 minutes; else 409), only known slots were sent, every required slot
  is present and valid (amount > 0, ≤ limit, 2 decimals; phone, till, paybill, bank formats), the
  source account is the caller's own, and the balance is sufficient (else 400). Any failure rolls
  back; nothing is half-done. A failed confirm leaves the action pending so it can be corrected.
- Internal transfers write both legs (same reference). The receipt is derived from the transaction row.
- Money-moving intents always route to `confirm`, never `direct`; a transfer phrased as a question
  goes to `llm` (action guard). Unexpected router output falls back to `llm_pending`.
- Every chat message is written to `router_audit` (intent, route, score, margin, reasons, latency).
- The `llm` route (Gemini fallback) is not built yet: the reply is `llm_pending`, asking the
  customer to rephrase; it is logged and audited.
- JWT (HS256) with expiry, bcrypt passwords, CORS limited to configured origins, ports bound
  to localhost except the frontend.

## Running in the cloud

- **One VM with Docker** is enough: e.g. 2 vCPU / **4 GB RAM** (the CPU model needs ~1.5-2 GB),
  `docker compose up -d --build`, a reverse proxy with TLS in front of port 3000.
- **Model weights:** either bake them into the image (copy the HF cache folder in at build time;
  bigger image, no host dependency) or keep them on a volume/disk mounted read-only as here.
  Keep `HF_HUB_OFFLINE=1` either way.
- Set a strong `JWT_SECRET` and Postgres password; don't publish the DB port; take backups of the volume.
- **Never use real customer data with the free Gemini tier** (the future LLM fallback): free-tier
  inputs may be used by Google to improve its products. Use a paid tier / Vertex AI with a data
  processing agreement, or keep the fallback off.
