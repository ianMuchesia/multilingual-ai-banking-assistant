# Baseline: gemma + logreg (frozen)

The "before" picture for Nia v2. Do not edit these files or re-run over them.
Every later change (LoRA, ONNX, INT8, distillation) is compared to this.

## What was measured

| Item | Value |
|---|---|
| Date | 2026-11-05 |
| Git commit | a9d9ff5 (branch v2) |
| Model | google/embeddinggemma-2 |
| Scoring | logreg, C=10 (picked by 5-fold CV), rules on, action guard on |
| Dials | threshold 0.75, margin 0.50 |
| Training data | 624 examples, train_sha8 fb2d35fb |
| Exam | test_synthetic, 298 sentences, used once |

## Results

| Metric | Overall | English | Kiswahili | Sheng |
|---|---|---|---|---|
| Sentences | 298 | 98 | 100 | 100 |
| Top-1 accuracy | 86.6% | 90.8% | 77.0% | 92.0% |
| Coverage (answered without LLM) | 27.9% | 44.9% | 17.0% | 22.0% |
| Critical errors | 0 | 0 | 0 | 0 |
| Minor errors | 0 | 0 | 0 | 0 |

215 messages went to the LLM. The router's top guess was already right for 175 of them.

## Machine

| Item | Value |
|---|---|
| CPU | 11th Gen Intel Core i7-1185G7 @ 3.00GHz, 8 threads |
| GPU | none used (CUDA not available) |
| RAM | 15 GiB |
| Python | 3.11.2 |
| torch | 2.10.0+cu128 |
| scikit-learn | 1.9.1 |
| numpy | 2.4.2 |
| transformers | 5.22.1 |

## Limits

- The exam is synthetic, not real customer messages.
- The dials were chosen on held-out training data, not on the exam.
- 298 sentences is small, so small differences between models may be noise.

## Known issues, left unchanged on purpose

- The statement rule gives margin 0, so those messages always go to the LLM, never to reject.
- "je kutuma pesa ni vipi" slips past the question guard, because "vipi" is not in its word list.
