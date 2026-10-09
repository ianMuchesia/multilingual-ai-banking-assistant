"""Embed a few sentences and show how similar each pair is (cosine similarity, 1.00 = identical).

    python -m scripts.sanity_check --backend gemma
    python -m scripts.sanity_check --backend gemma --texts "how do I send money to KCB" "send 5000 to KCB"

Experiment flags (each one deliberately changes a safe default):
    --dim 256            smaller vectors: cheaper, how much quality is lost?
    --no-prefix          skip "task: classification | query: ": does the prefix matter?
    --dtype float16      gemma only: known to give NaN/garbage; the checks should catch it
    --no-wrap            gemini only: list of strings -> ONE vector; the count check should fire
"""

import argparse
import logging
import sys
import time

import numpy as np

from src.config import GEMMA_DTYPES, load_settings, with_overrides
from src.embeddings import BACKENDS, EmbeddingError, QuotaExceededError, make_embedder
from src.logging_setup import setup_logging

DEFAULT_TEXTS = [
    "what's my balance",            # balance_inquiry, en
    "salio langu ni ngapi",         # balance_inquiry, sw
    "send 5000 to my KCB account",  # external_transfer
    "pay till number 123456",       # lipa_na_mpesa
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed sentences and print their similarity matrix.")
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--dim", type=int, help="vector size (default from config: 768)")
    parser.add_argument("--no-prefix", action="store_true", help="do not add the task prefix")
    parser.add_argument("--dtype", choices=GEMMA_DTYPES, help="gemma only: model precision")
    parser.add_argument("--no-wrap", action="store_true", help="gemini only: send a plain list of strings")
    parser.add_argument("--texts", nargs="+", default=DEFAULT_TEXTS, help="sentences to compare (2 or more)")
    args = parser.parse_args()

    if len(args.texts) < 2:
        parser.error("--texts needs at least 2 sentences")
    if args.dtype and args.backend != "gemma":
        parser.error("--dtype only applies to --backend gemma")
    if args.no_wrap and args.backend != "gemini":
        parser.error("--no-wrap only applies to --backend gemini")
    return args


def format_matrix(texts: list[str], sims: np.ndarray) -> str:
    lines = [f"  [{i}] {t}" for i, t in enumerate(texts)]
    lines.append("")
    lines.append("      " + "".join(f"{f'[{j}]':>6}" for j in range(len(texts))))
    lines += [f"  [{i}] " + "".join(f"{v:6.2f}" for v in row) for i, row in enumerate(sims)]
    return "\n".join(lines)


def format_closest(texts: list[str], sims: np.ndarray) -> str:
    """For each text, its most similar OTHER text."""
    others = sims.copy()
    np.fill_diagonal(others, -np.inf)
    lines = ["Closest match:"]
    for i, text in enumerate(texts):
        j = int(np.argmax(others[i]))
        lines.append(f"  [{i}] {text!r:<35} -> [{j}] {texts[j]!r}  ({sims[i, j]:.2f})")
    return "\n".join(lines)


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = with_overrides(
        load_settings(),
        dim=args.dim,
        use_prefix=False if args.no_prefix else None,
        gemma_dtype=args.dtype,
        gemini_wrap_contents=False if args.no_wrap else None,
    )

    started = time.perf_counter()
    embedder = make_embedder(args.backend, settings)
    loaded = time.perf_counter()
    try:
        vectors = embedder.embed(args.texts)
    except QuotaExceededError as e:
        logging.error("STOPPED: %s", e)
        return 2
    except EmbeddingError as e:
        logging.error("CHECK FAILED: %s", e)
        return 1
    finished = time.perf_counter()

    sims = vectors @ vectors.T  # unit-length rows, so dot product = cosine similarity
    prefix = "on" if embedder.prefix else "OFF"
    print(f"\n{embedder.model_id}  dim={embedder.dim}  prefix={prefix}\n")
    print(format_matrix(args.texts, sims))
    print()
    print(format_closest(args.texts, sims))
    print(f"\nload {loaded - started:.1f}s, embed {len(args.texts)} texts {finished - loaded:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
