# Nia

**A multilingual intent router for banking.** Nia reads a customer's message in English, Kiswahili or Sheng, decides what they want, and routes it safely: answer directly, ask for confirmation, decline, or hand over to an LLM when unsure. It never moves money without an explicit confirmation.

*Nia* is Swahili for *intention*. The demo bank in this repo is the fictional **Benki Yetu**, and its assistant is **Benki AI**.

```
"salio langu ni ngapi"             -> balance_inquiry   -> answer directly
"tuma 2k kwa KCB yangu"            -> external_transfer -> review and confirm
"how do I send money to KCB?"      -> transfer_help     -> answer directly
"nimeibiwa pesa na mtu wa simu"    -> unsupported       -> decline politely
"ni swali, hii process ikoje"      -> not sure          -> hand over to the LLM
```

## Why

Kenyan customers rarely write the way banking chatbots expect. They mix English, Kiswahili and Sheng in one sentence ("nicheki balance ya savings", "doh imebaki aje"), abbreviate ("bal?", "lst 5 txns") and name other banks and wallets freely. Nia is an experiment in handling that cheaply and locally: a small open embedding model and a linear classifier do most of the work, rules handle facts a model can't know, and an LLM is only consulted when the router is unsure.

## How it works

```
message
  -> EmbeddingGemma (local, CPU)          768-dim sentence vector, task prefix "classification"
  -> logistic regression (softmax)        one probability per intent (10 intents)
  -> rules                                facts a model can't know:
                                            bank rule: Benki Yetu / "same bank" = internal,
                                                       another bank or M-Pesa = external
                                            statement rule: a statement for someone else = unsupported
  -> threshold + margin + action guard    sure enough? clearly ahead of the runner-up?
                                            money-moving intent phrased as a question?
  -> route: direct | confirm | reject | llm
```

- **Category drives the route.** `view` and `info` intents are answered directly; `action` intents (internal transfer, external transfer, Lipa na M-Pesa) always go to **confirm**; `unsupported` is declined.
- **The router never executes anything.** In the app, money moves only in a separate confirm endpoint, inside one database transaction, after ownership, expiry, required-field and balance checks.
- **Every decision is explainable.** The router returns the top intents, the nearest training examples and the reasons, and the app shows them under "Why this answer?".

## Results

The exam is `test_synthetic.json`: 298 messages (about 100 per language), written by a different model than the training data and never used for training or tuning. Dials are tuned on held-out training scores only.

| EmbeddingGemma + | First guess right | Answered without the LLM | Correct when answering alone | Critical errors |
|---|---|---|---|---|
| nearest examples (top-3 mean) | 76.5% | 13.4% | 97.5% | 1 |
| logistic regression | 83.6% | 24.5% | 98.6% | 1 |
| **logistic regression + rules** | **86.6%** | **27.9%** | **100%** | **0** |

By language (logistic regression + rules): English 91%, Kiswahili 77%, Sheng 92%.

A **critical error** is a message the router handled on its own with the wrong intent, where money or fraud was involved.

What the experiments showed (full write-up in [intent-router/notes/findings.md](intent-router/notes/findings.md)):

- **The task prefix matters.** Without `task: classification | query:`, "what's my balance" matched "send 5000 to KCB".
- **Embeddings measure topic, not intent.** "How do I send money to KCB" and "send 5000 to KCB" score 0.87 on both EmbeddingGemma and Gemini embeddings. A question-phrasing guard and the LLM fallback handle this.
- **A trained linear head beats nearest-neighbour scoring**, and the paired comparison is one-sided. A small MLP was overconfident and was rejected.
- **Some distinctions are facts, not language.** Whether "my Co-op account" is internal depends on which bank *we* are. A config file and a rule fixed every internal/external error (16/30 to 28/30 internal transfers correct).
- **What's left is confidence:** most messages sent to the LLM already had the correct top intent. That is the target of the fine-tuning step.

## Repository layout

```
intent-router/     the ML part (Python)
  data/            intents.json (catalog), examples/train.json, test.json, test_synthetic.json
  config/          router.json (dials per backend and method), bank.json (who "we" are)
  src/             embeddings, scoring, rules, router, evaluation, fine-tuning
  scripts/         check_data, build_index, sanity_check, route, evaluate, finetune
  notes/           findings.md: every experiment and what it showed
  eval/results/    evaluation reports (JSON + per-sentence CSV), with earlier versions in v1/, v2/
app/               full-stack simulation of Benki Yetu
  backend/         FastAPI + PostgreSQL: auth, accounts, transactions, chat, confirm/cancel
  frontend/        React + TypeScript: dashboard, Benki AI chat, "Why this answer?", confirm sheet
  docker-compose.yml
```

## Quick start

### Run the app (Docker)

```cmd
cd app
copy .env.example .env
```

In `app\.env`, set `HF_CACHE_DIR` to your Hugging Face cache (e.g. `C:\Users\<you>\.cache\huggingface`) and `JWT_SECRET` to a long random string. Use `ROUTER_MODE=stub` for a first look without the model, or `ROUTER_MODE=gemma` for the real router. Then:

```cmd
docker compose up --build
```

Open http://localhost:3000 and sign in as `amina`, `brian` or `wanjiku` with password `password123` (demo users only).

### Work on the router

```cmd
cd intent-router
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

python -m scripts.check_data
python -m scripts.build_index --backend gemma
python -m scripts.build_index --backend gemma --split test_synthetic
python -m scripts.evaluate --backend gemma --test test_synthetic
python -m scripts.route --backend gemma --local-only
```

See [intent-router/README.md](intent-router/README.md) for every flag, and [app/README.md](app/README.md) for the app's architecture and safety design.

## Evaluation discipline

- **Train and exams never overlap.** `check_data` fails if any sentence (case- and whitespace-insensitive) appears in two files.
- **Nothing is tuned on an exam.** Thresholds are chosen on leave-one-out (similarity scorers), 5-fold cross-validation (classifiers) or a calibration split (fine-tuned encoders), then applied to the exam once.
- **Paired counts, not just percentages.** With 50 to 300 test sentences, a few points can be noise. Comparisons report "A right / B wrong" against "B right / A wrong".
- **Every result is stamped** with the hash of the `train.json` that produced it.

## Data

- **Catalog:** 10 intents in [intent-router/data/intents.json](intent-router/data/intents.json), each with a category, a description, includes/excludes and slots.
- **Training:** 624 sentences (172 English, 233 Kiswahili, 219 Sheng). Hand-written and model-assisted, then reviewed: mislabelled internal/external transfers were corrected, and anything copied from a test set or sounding unnatural was removed.
- **Exams:** `test.json` (50) and `test_synthetic.json` (298). A test set written by native speakers who haven't seen the training data is still to come, and will give the most trustworthy number.
- All data is synthetic. No real customer messages are used.

## Roadmap

- [x] Embedding backends (local EmbeddingGemma, Gemini as a comparison baseline), cached indexes
- [x] Router with threshold, margin and action guard
- [x] Evaluation harness: held-out tuning, critical errors, per-language results, paired counts
- [x] Logistic regression scorer, bank rule and third-party statement rule
- [x] Full-stack simulation: FastAPI, PostgreSQL, React, Docker
- [ ] Fine-tune EmbeddingGemma (SetFit / LoRA) to raise confidence (code ready, results pending)
- [ ] LLM fallback with retrieved examples: structured JSON answers, a "clarify" option, and no way to skip confirmation
- [ ] End-to-end evaluation: accuracy, LLM call rate and latency with the fallback in place
- [ ] Independent test set from native Kiswahili and Sheng speakers

## Limitations

- **A demo, not a bank.** The bank, users and transactions are fictional.
- **The free Gemini tier is not suitable for customer data.** Google may use free-tier inputs to improve its products. A production version would need compliance approval for a paid API, or a local LLM.
- **Small exams.** Per-language results rest on about 100 sentences each, and Kiswahili is still the weakest language.
