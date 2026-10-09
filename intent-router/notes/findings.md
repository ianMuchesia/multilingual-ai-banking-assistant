# Step 3 findings: embedding experiments

Date: 2026-10-09. Machine: Windows laptop, CPU only (no GPU).
Models: `google/embeddinggemma-2` (local) and `gemini-embedding-2` (API, free tier).

Scores are cosine similarity: 1.00 = same meaning, lower = less related.
**A score only means something compared with the other scores in the same run.**

Default test sentences:

| # | Sentence | Intent |
|---|----------|--------|
| [0] | what's my balance | balance_inquiry (en) |
| [1] | salio langu ni ngapi | balance_inquiry (sw) |
| [2] | send 5000 to my KCB account | external_transfer |
| [3] | pay till number 123456 | lipa_na_mpesa |

## 1. Baseline (gemma)

Command: `python -m scripts.sanity_check --backend gemma` (run twice)

```
         [0]   [1]   [2]   [3]
  [0]   1.00  0.70  0.66  0.68
  [1]   0.70  1.00  0.62  0.65
  [2]   0.66  0.62  1.00  0.72
  [3]   0.68  0.65  0.72  1.00
```

- "what's my balance" and "salio langu ni ngapi" are each other's closest match ✅ (0.70)
- KCB transfer and till payment are each other's closest match (0.72): both are payments, so related but different intents.
- Load time: run 1 **18.2s** (downloaded leftover tokenizer/config files, cold disk), run 2 **8.8s**.
- Embed time: **~0.25s for 4 sentences**. Loading happens once at startup, so per-message speed is what customers feel.
- Scores were **identical on both runs**: the model is deterministic.
- ⚠️ All scores sit between 0.62 and 0.72. "what's my balance" scores 0.70 with its Swahili twin but 0.68 with the till payment: **a gap of only 0.02** between same meaning and different meaning.

## 2. Without the prefix

Command: `python -m scripts.sanity_check --backend gemma --no-prefix`

```
         [0]   [1]   [2]   [3]
  [0]   1.00  0.67  0.70  0.68
  [1]   0.67  1.00  0.66  0.70
  [2]   0.70  0.66  1.00  0.70
  [3]   0.68  0.70  0.70  1.00
```

- en/sw balance: 0.70 → **0.67**. They are **no longer each other's closest match** ❌
- "what's my balance" → closest is "send 5000 to KCB" (0.70). A balance question matched to a money transfer.
- "salio langu ni ngapi" → closest is "pay till number" (0.70).
- Almost every score is ~0.70: without the task label the model doesn't know what kind of similarity to measure.
- **Conclusion: the prefix (`task: classification | query: `) is required.** It must be applied to both the training examples and the customer messages, which is why the code applies it in one place.

## 3. The float16 failure

Command: `python -m scripts.sanity_check --backend gemma --dtype float16`

- **No NaN, no error.** Scores identical to float32 at 2 decimals.
- Embedding was **~5× slower**: 1.40s vs 0.25s. Most CPUs aren't built for float16 maths. This also confirms the model really ran in float16.
- The known failure (NaN / degraded vectors) **did not reproduce** on CPU with short sentences. It's reported mainly on GPUs and with longer inputs.
- **Conclusion:** float16 gives no benefit here (same quality, much slower) and is known to be risky elsewhere. Keep float32. If it ever produces NaN, the checks in `Embedder.embed()` will stop it.

## 4. Smaller vectors

Commands: `--dim 256`, then `--dim 128`

| dim | en/sw balance | balance vs KCB | balance vs till | Correct closest match? |
|-----|---------------|----------------|-----------------|------------------------|
| 768 | 0.70 | 0.66 | 0.68 | ✅ |
| 256 | 0.72 | 0.70 | 0.69 | ✅ (gap still ~0.02) |
| 128 | 0.76 | 0.81 | 0.79 | ❌ balance → KCB transfer |

- Smaller vectors push **all** scores up and closer together. **Higher scores ≠ better.**
- 256 still picks the right matches; 128 breaks (balance matched to a transfer, Swahili balance matched to the till).
- **Conclusion: keep 768.** The storage saving is negligible: 200 examples × 768 floats ≈ 0.6 MB.

## 5. Hard pairs

Command: `python -m scripts.sanity_check --backend gemma --texts "..." "..."`

| Pair | Score | Same action? |
|------|-------|--------------|
| "how do I send money to KCB" vs "send 5000 to KCB" | **0.87** | ❌ No (transfer_help vs external_transfer) |
| "show my statement" vs "send my statement to my landlord" | 0.63 | ❌ No (full_statement vs unsupported) |
| "naeza cheki balance yangu" vs "nimebaki na doh ngapi" | 0.70 | ✅ Yes (both balance_inquiry, Sheng) |

(A run with the literal placeholders "your sheng sentence 1/2" scored 0.98. That is meaningless: the two strings are almost identical.)

- ⚠️ **The help-vs-transfer pair scored higher (0.87) than a same-meaning Sheng pair (0.70).** Shared words ("send", "money", "KCB") fool the model more than the meaning does.
- That's the dangerous direction: a customer asking *how* to send money could be routed to *sending* money.
- The statement pair scored low (0.63), so the model sees the difference. But in the router, "send my statement to my landlord" may still land nearest to `full_statement` examples rather than `unsupported`.
- Sheng is the weakest area: two Sheng sentences with the same meaning only reached 0.70.
- **Conclusion: a fixed threshold ("above 0.8 = same intent") will not work.** The router needs:
  1. comparison against all 20 examples per intent, not one;
  2. a **margin rule**: if the top two intents are close, don't guess;
  3. a **Gemini Flash fallback** for those uncertain cases;
  4. **confirmation for every money-moving intent** as the last safety net.

## 6. Build the index

Command: `python -m scripts.build_index --backend gemma`

- First run: 200 examples, load **9.2s**, embed **12.2s** (~0.06s per sentence). Saved `cache/gemma_768.npz`, vectors **(200, 768) float32** ✅
- Second run: `up to date (train.json unchanged), skipping` ✅
- After adding one space to `train.json`: change detected, rebuilt (load 8.9s, embed 10.8s) ✅
- To do: confirm the space was removed from `train.json`, then rebuild once so the index matches the original file.

## 7. Offline test

Wifi off. Note: the terminal is **cmd**, so the command is `set HF_HUB_OFFLINE=1` (the PowerShell form `$env:HF_HUB_OFFLINE = "1"` fails in cmd).

| Run | Load time | Result |
|-----|-----------|--------|
| Wifi off, offline setting NOT applied | **27.9s** | Worked, after 4 failed retries to reach huggingface.co (~19s wasted) |
| Wifi off, `set HF_HUB_OFFLINE=1` | **7.0s** | Worked, no retries, no warnings |

- Scores identical to online in both cases ✅
- **EmbeddingGemma runs fully offline: customer messages never need to leave the bank.**
- Improvement for later: load the model with "local files only" in production, so startup never depends on reaching Hugging Face.

## 8. Gemini baseline

Commands: `python -m scripts.sanity_check --backend gemini`, then with `--no-wrap`

```
         [0]   [1]   [2]   [3]
  [0]   1.00  0.82  0.72  0.67
  [1]   0.82  1.00  0.72  0.65
  [2]   0.72  0.72  1.00  0.70
  [3]   0.67  0.65  0.70  1.00
```

| | Gemma (local) | Gemini (API) |
|---|---|---|
| en/sw balance score | 0.70 | **0.82** |
| Gap to next closest | 0.02 | **0.10** |
| "send 5000 to KCB" closest to | till (0.72), makes sense | Swahili balance (0.72, tied with English balance) ❓ |
| Load | 7–9s, once | 1.1s |
| Embed 4 sentences | **0.25s** | 1.51s (network) |
| Offline / data stays in bank | ✅ | ❌ |
| Limits | none | free tier: 100 texts/minute |

- Gemini separates the balance pair much more clearly, but is not perfect: it placed the KCB transfer as close to the balance questions as to anything else.
- **Hard pair on Gemini:** "how do I send money to KCB" vs "send 5000 to KCB" = **0.87, exactly the same as Gemma.**
  So this is not a weakness of one model. **Embeddings measure what a sentence is *about* (sending money to KCB), not what the customer wants to *do* (ask a question vs give an order).** A better embedding model will not fix it; the router design has to.
- `--no-wrap`: **the count check fired** ✅
  `CHECK FAILED: gemini-embedding-2: sent 4 texts but got back shape (1, 768). One vector per text is required.`
  Sent as a plain list of strings, Gemini merges all 4 sentences into ONE vector. Without the check, that vector would silently have been used as if it belonged to the first sentence.
- Earlier, `build_index --backend gemini` hit a **429 quota error** with a 1s pause between batches of 25. The free tier counts each text as one request (100/minute), so the pause is now 16s.

# Step 4 findings: first router runs

Router: `topk_mean` (k=3), action guard on. Placeholder dials: gemma threshold 0.70 / margin 0.03, gemini 0.75 / 0.05.
Messages were made up by hand (none from `test.json`). Some were phrased slightly differently between the two runs.

## Gemma vs Gemini on similar messages

| Message | Meant | Gemma top guess → route | Gemini top guess → route |
|---|---|---|---|
| niaje | unsupported | find_transaction ❌ → llm | **unsupported ✅ → reject** (margin 0.066) |
| process ya kutuma doh mpesa | transfer_help (question) | external_transfer ❌ → **CONFIRM** ⚠️ (margin 0.031) | external_transfer ❌ → llm (margin 0.027) |
| to find the amount of money i spent last week | mini_statement | balance_inquiry ❌ → llm | **mini_statement ✅** → llm |
| my expenditure in the past quarterly | full_statement | **full_statement ✅** → llm | mini_statement ❌ (by 0.004) → llm |
| a past transfer with "mzae" (Sheng)¹ | find_transaction | external_transfer ❌ → llm | **find_transaction ✅** → llm (all 3 nearest correct) |
| ni swali… process ikoje | transfer_help | find_transaction ❌ → llm | unsupported ❌ → llm |
| how to send money | transfer_help | **transfer_help ✅** → llm (margin 0.024) | (not tried) |

¹ Gemma: "naeza cheki pesa nilitumia mzae jana". Gemini: "nadai kujua doh mzae alinitumia juzi".

| | Gemma | Gemini |
|---|---|---|
| Correct top guess (rough, ~8 messages) | ~3 of 8 | ~5 of 8 |
| Sent to llm | 7 of 8 | 7 of 8 |
| Margins | 0.003–0.031 | 0.004–0.066 |
| Latency per message | ~100–240 ms | ~900–1150 ms (network) |

## What we learned

- **The one dangerous result:** gemma sent "process ya kutuma doh mpesa", a *question*, to **confirm** (external_transfer). The action guard missed it because "process ya" is not in its keyword list. In a real app the customer would have seen a transfer confirmation screen when they only wanted an explanation. **Nothing was executed**: that is exactly what the confirmation step is for. Adding "swali" or "process" to the guard won't fix this for good; the next phrasing will slip past too. Only the LLM (step 5) or a trained classifier fixes it properly.
- **The router is safe but unsure.** When its top guess was wrong, it nearly always routed to llm instead of acting.
- **Gemini understands Swahili/Sheng better.** Gemma matches Swahili sentences on shared words (*pesa, jana, nataka*), so every intent scores ~0.83–0.87 and nothing stands out.
- **Hard for both models:**
  - **mini_statement vs full_statement**: the difference is a time range ("last week" vs "last quarter"), and embeddings pay little attention to time words. In production, the date range is usually detected separately with simple rules (the backend needs it as a parameter anyway) rather than relying on the embedding.
  - **transfer_help vs external_transfer**: asking how vs doing it (the 0.87 problem).
- **Some messages are genuinely unclear**, e.g. "ni swali, hii process ikoje" doesn't say *which* process. For those, llm (or asking the customer) is the right answer.
- **The method is the main limit, more than the model.** Nearest-example scoring gives tiny margins for intents that share a topic, on both backends. A trained classifier is the next candidate, but only **after** the evaluation gives us a baseline to beat.

# Overall summary (step 3)

**Gemma or Gemini?**
- Gemini separates meanings more clearly (en/sw gap 0.10 vs 0.02).
- Gemma is faster per message, free, unlimited, and keeps customer data inside the bank.
- 4 sentences are too few to choose. **The decision should come from the evaluation on the 50 held-out test sentences.**

**Settings confirmed:**
- prefix ON (required)
- float32 (float16 gives no gain on CPU)
- dim 768 (128 breaks; the savings are negligible)

**Biggest risk for the router:**
- Sentences that **share words but need different actions**, especially "how do I send money" (help) vs "send money" (actual transfer). **Both Gemma and Gemini scored that pair 0.87**: it's a limit of embeddings in general, not of one model.
- Sheng is also weak.
- Mitigation: margin rule + Gemini Flash fallback + mandatory confirmation for all money-moving intents.

**Open items:**
- Remove the test space from `train.json` and rebuild the gemma index.
- Build the gemini index (`build_index --backend gemini`, ~2 min with free-tier pacing).
- Production: load Gemma with local files only.

# Steps 6-7 findings: classifier, more data, rules (2026-10-09)

## Data versions

| Version | train.json | Added |
|---|---|---|
| v1 | 200 (128 en / 46 sw / 26 sheng), sha 7864418e | original |
| v2 | 330, sha 420cceb1 | +130 sw/sheng written by Claude, targeting the confusions |
| v3 | 624, sha 49709088 | +294 written by Gemini, after review: 18 "internal" examples naming another bank moved to external, 21 removed (1 copied from test.json, ambiguous or fake-sounding Sheng). lipa_na_mpesa got no new examples (Gemini skipped it). |

Exams: `test.json` (50, ~10 per language: too small to separate methods) and **`test_synthetic.json` (298, ~100 per language, written by OpenAI, i.e. a different model than the training data)**. 2 test_synthetic sentences duplicated train and were removed; 15 were edited to say "Benki Yetu" (see the bank rule below).

## Classifier: logistic regression wins, MLP rejected

On test.json, v1: gemma top-1 74% (topk_mean) -> **86% (logreg)**, paired 7 vs 1. Gemini 90% -> 88% (no change). The MLP was overconfident or broken (gemma v1: 32%; gemini: 2 critical errors). Logreg is the default scorer.

## v1 -> v2 -> v3 on test.json (50), logreg, no rules

| | v1 (200) | v2 (330) | v3 (624) |
|---|---|---|---|
| gemma top-1 | 86% | 80% | 84% |
| gemma coverage | 40% | 50% | 32% |
| gemma critical | 1 | 1 | 1 (always "move money to my Co-op account") |
| gemma sw / sheng top-1 | 82% / 90% | 64% / 70% | 73% / 70% |
| gemini top-1 / coverage / critical | 88% / 82% / 0 | 88% / 82% / 1 | not run (daily quota) |

- These swings are 2-4 sentences: **test.json cannot measure the effect of the data.** The held-out train score (5-fold CV) is more stable and rose: gemma 70.5% (v1) -> 80% (v2).
- The "Swahili 45%" from earlier was gemma **topk_mean** v1; with **logreg** it was already 82%. topk_mean sw went 45% -> 64% (v3).

## The big exam: test_synthetic (298), gemma, v3

| gemma | top-1 | coverage | acc on covered | critical | en / sw / sheng |
|---|---|---|---|---|---|
| logreg, no rules | 83.6% | 24.5% | 98.6% | 1 | 85 / 76 / 90% |
| **logreg + rules** | **86.6%** | **27.9%** | **100%** | **0** | **91 / 77 / 92%** |
| topk_mean + rules | 81.2% | 14.4% | 100% | 0 | 88 / 76 / 80% |
| mlp + rules | 79.5% | 52.7% | 93.6% | 7 | rejected |

Paired (logreg): rules right / no-rules wrong = **9**, reverse = **0**.

## Rules: facts a model can't know

The bank is now the fictional **Benki Yetu** (`config/bank.json`). Before this, the data disagreed on what "internal" means: our training data treated any named bank as external, OpenAI's exam assumed the customer banks at KCB/Absa/NCBA ("Absa hapa hapa" = internal). No model can learn that; it's a definition.

- **Bank rule:** a transfer naming another bank or wallet -> external; naming Benki Yetu or "same bank / hapa hapa" -> internal. internal_transfer on test_synthetic: 16/30 -> **28/30**.
- **Statement rule:** a statement for an email address or a third party -> unsupported (catalog excludes it).
- Rules only re-rank; the threshold/margin checks still run after them.

## What's left

- **Confidence, not knowledge:** of the 215 messages gemma+logreg+rules sent to the LLM, **175 already had the correct top intent**. Coverage is 28%.
- **Swahili** is the weakest language (77%).
- **lipa_na_mpesa:** 6/30 mistaken for transfers (no new training data). **unsupported:** 21/30 (the rest pulled towards real intents, but sent to the LLM).
- Gemini v3 numbers are missing: the free tier's daily quota ran out (~1,000+ embedding calls in a day).
