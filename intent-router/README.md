# intent-router

Routes customer banking messages to a fixed catalog of intents.

- **Primary routing: embeddings.** Each message is embedded and matched against the labelled examples in `data/examples/train.json`.
- **Fallback: Gemini Flash.** When the embedding match is uncertain, Gemini Flash classifies the message against the catalog.
- **Money-moving intents always require confirmation.** `action` intents (`internal_transfer`, `external_transfer`, `lipa_na_mpesa`) must be explicitly confirmed by the customer, however confident the routing is.
- **No forced matches.** Anything outside the catalog goes to `unsupported`.

## Layout

```
intent-router/
├── data/
│   ├── intents.json            # intent catalog
│   └── examples/
│       ├── train.json          # examples the router matches against
│       └── test.json           # held-out evaluation set, never used for training
├── config/
│   └── router.json             # router dials per backend: threshold, margin, scoring, guard
├── src/
│   ├── config.py               # all settings: paths, model ids, dims, prefix, API limits
│   ├── data.py                 # loading the catalog and examples
│   ├── index.py                # EmbeddingIndex: save/load cached vectors
│   ├── scoring.py              # per-intent scores: max, topk_mean, centroid
│   ├── question_guard.py       # "does this read like a question?" keyword check
│   ├── router.py               # Router.route(text) -> RouteDecision (never executes anything)
│   ├── evaluate.py             # leave-one-out tuning, test scoring, error types
│   ├── finetune.py             # contrastive fine-tuning of EmbeddingGemma -> gemma-ft
│   └── embeddings/
│       ├── base.py             # Embedder contract: one unit-length vector per text
│       ├── gemma.py            # google/embeddinggemma-2, local
│       ├── gemma_ft.py         # the fine-tuned EmbeddingGemma from models/gemma-ft
│       └── gemini.py           # gemini-embedding-2, API
├── scripts/                    # command-line entry points (thin; logic lives in src/)
│   ├── check_data.py
│   ├── sanity_check.py
│   ├── build_index.py
│   ├── route.py
│   └── evaluate.py
├── notes/findings.md           # experiment notes
├── eval/results/               # evaluation output
├── cache/                      # built indexes (git-ignored)
├── models/gemma-ft/            # fine-tuned model, calibration split, metadata (git-ignored)
├── requirements.txt
└── .env.example                # copy to .env and set GEMINI_API_KEY
```

## Setup

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
copy .env.example .env          # then fill in GEMINI_API_KEY
```

## Commands

Run from the `intent-router` folder:

```sh
python -m scripts.check_data                       # validate the data files
python -m scripts.sanity_check --backend gemma     # 4-sentence similarity matrix
python -m scripts.build_index  --backend gemma     # -> cache/gemma_768.npz
python -m scripts.build_index  --backend gemini    # -> cache/gemini_768.npz (~2 min, free-tier pacing)
```

`check_data` checks that intents match the catalog, every example has `text` and `lang` (`en`/`sw`/`sheng`), there are no duplicates, and nothing appears in both train and test. It exits 1 on any failure.

`build_index` skips the work if the index was already built from the current `train.json`. Pass `--force` to rebuild, or `--dim 256` to build a smaller index.

## Experiment flags (`sanity_check`)

The defaults are the safe production settings. Each flag changes one on purpose, so you can see what it does:

| Flag | Backend | What it demonstrates |
|------|---------|----------------------|
| `--texts "a" "b" ...` | both | Compare your own sentences instead of the default four |
| `--dim 256` / `--dim 128` | both | Smaller vectors are cheaper to store; how much quality do they cost? |
| `--no-prefix` | both | Skips `task: classification \| query: `; shows whether the prefix matters |
| `--dtype float16` | gemma | Known to give NaN or garbage vectors; the checks should stop it |
| `--no-wrap` | gemini | Sends a plain list of strings, which comes back as ONE vector; the count check should fire |

Offline run (proves gemma needs no internet): before the command, run `set HF_HUB_OFFLINE=1` in cmd, or `$env:HF_HUB_OFFLINE = "1"` in PowerShell. Undo with `set HF_HUB_OFFLINE=` / `$env:HF_HUB_OFFLINE = ""`.

Record what you see in [notes/findings.md](notes/findings.md).

## Embedding backends

| Backend  | Model                     | Runs           | Needs                         |
|----------|---------------------------|----------------|-------------------------------|
| `gemma`  | `google/embeddinggemma-2` | locally on CPU | ~1.5 GB model download (once) |
| `gemini` | `gemini-embedding-2`      | Gemini API     | `GEMINI_API_KEY` in `.env`    |
| `gemma-ft` | `google/embeddinggemma-2` fine-tuned on `train.json` | locally on CPU | `python -m scripts.finetune` first |

To change a model, the dimension, the prefix or the rate limits, edit `src/config.py`.

## Routing

```sh
python -m scripts.route --backend gemma                         # interactive
python -m scripts.route --backend gemma --text "salio langu"    # one message
```

For each message it shows the route, the top 3 intents with scores, the margin, the 3 nearest training examples, the reasons, and the latency. The router only decides; it never executes anything.

| Route | When |
|-------|------|
| `llm` | best score below the threshold, **or** best minus second-best below the margin, **or** a money-moving intent phrased as a question (action guard) |
| `reject` | confident, and the intent is `unsupported` |
| `confirm` | confident, and the intent moves money (`action`) |
| `direct` | confident, and the intent is `view` or `info` |

The dials live in [config/router.json](config/router.json), with a threshold and margin **per backend** because gemma and gemini score on different scales. The current values are placeholders; step 6 calibrates them. Flags override them for one run:

| Flag | Effect |
|------|--------|
| `--scoring max \| topk_mean \| centroid` | best single example / mean of the k best / cosine to the intent's average |
| `--scoring logreg \| mlp` | a classifier trained on the embeddings; score = probability. Each method has its own threshold/margin in `config/router.json` |
| `--k 5` | examples averaged per intent with `topk_mean` |
| `--threshold 0.75 --margin 0.05` | higher → more messages go to the LLM; lower → more routed directly (and more mistakes) |
| `--no-guard` | switch off the action guard to see what it catches |
| `--local-only` | gemma: load from the local cache only, never contact Hugging Face |

**Rules** ([src/rules.py](src/rules.py), bank identity in [config/bank.json](config/bank.json)) run after the scorer, for facts a model can't know:

- **Bank rule:** for a transfer, naming another bank or a wallet (KCB, Equity, M-Pesa…) means `external_transfer`; naming Benki Yetu or "same bank / hapa hapa" means `internal_transfer`.
- **Statement rule:** a statement for someone else (an email address, an accountant, a landlord) is `unsupported`.

The confidence checks still run after the rules. `--no-rules` (in `route.py` and `evaluate.py`) switches them off to measure what they add.

The router refuses to start if the index is stale (`train.json` changed, or a different model, dim or prefix). Rebuild with `build_index`.

Don't test with sentences from `test.json`: tuning by eye on the test set makes the step 6 scores meaningless.

## Evaluation

```sh
python -m scripts.build_index --backend gemma --split test   # embed the 50 test sentences once
python -m scripts.evaluate    --backend gemma                # all scoring methods, offline, instant
python -m scripts.evaluate    --backend gemini --scoring topk_mean

# second exam, written by a different model (OpenAI) than the training data
python -m scripts.build_index --backend gemma --split test_synthetic
python -m scripts.evaluate    --backend gemma --test test_synthetic
```

How it keeps the test score honest: **the dials are never tuned on `test.json`.**

1. **Leave-one-out on train:** each of the 200 training examples is scored against the other 199.
2. **Sweep:** threshold 0.50–0.95 (step 0.01) × margin 0–0.10 (step 0.005), using the router's real decision rules with the action guard on.
3. **Choose** the setting with zero critical errors and the highest coverage.
4. **Apply that one setting to the test set**, once.

| Term | Meaning |
|------|---------|
| coverage | share of messages the router handles itself (not sent to the LLM) |
| critical error | handled, wrong intent, and money or fraud is involved: predicted or true intent is an action, or the true intent is `unsupported` |
| minor error | handled, wrong intent, view/info only (or a valid request rejected) |
| llm, top-1 already right | sent to the LLM even though the top intent was correct; if this is high, the margin is too strict, not the model too weak |

Output: a report per scoring method (LOO-train vs test, per language, confusion matrix, every critical error, a risk-vs-coverage table), saved as `eval/results/{backend}_{scoring}.json` and `.csv` (one row per test sentence), then a table comparing every saved result.

With 50 test sentences, one error moves a score by 2% (10% for a 10-sentence language). Treat small gaps between methods as noise.

## Fine-tuning

`scripts.finetune` fine-tunes EmbeddingGemma SetFit-style: pairs of training sentences, same intent = positive (cosine pulled to 1), different intent = negative (pushed to 0), with the same `task: classification | query: ` prefix the router uses. LoRA by default (`--full` for full fine-tuning). The result is the `gemma-ft` backend; settings are in `FinetuneConfig` in `src/config.py`.

```sh
pip install -r requirements.txt                                      # adds peft, datasets, accelerate
python -m scripts.finetune                                           # -> models/gemma-ft/ (LoRA)
python -m scripts.build_index --backend gemma-ft --force             # -> cache/gemma-ft_768.npz
python -m scripts.build_index --backend gemma-ft --split test_synthetic --force
python -m scripts.evaluate    --backend gemma-ft --scoring logreg --test test_synthetic
```

Use `--force` on `build_index` after every fine-tuning run: the index check only notices a changed `train.json`, not a retrained model (`evaluate` and `route` do refuse a mismatched model).

**Keeping it honest.** 20% of `train.json` (stratified by intent and language, seed 42) is held out as a calibration split, saved to `models/gemma-ft/calibration.json`; the encoder never sees it. Leave-one-out or 5-fold CV on the other 80% would be optimistic, because the encoder was trained on those sentences. So for `gemma-ft`, `evaluate` fits the scorer on train minus calibration, scores the calibration sentences and chooses threshold/margin on those (`held_out_method: "calibration split"` in the results). Then it refits on all of train and scores the exam once, as for the other backends. `test.json` and `test_synthetic.json` are never used for training or tuning.

**What to compare** (`gemma` vs `gemma-ft`, `logreg`, exam `test_synthetic`): top-1 accuracy, coverage, critical errors (must stay 0), the Swahili row of the per-language table, and "llm, top-1 already right" (fine-tuning should mainly raise confidence, so this count should fall and coverage rise). The paired-counts table shows whether a top-1 difference is real or noise. The gemma-ft dials in `config/router.json` are placeholders copied from gemma; copy in the values `evaluate` chooses.
