"""Embed an example set and save it to cache/.

    python -m scripts.build_index --backend gemma                  # train -> cache/gemma_768.npz
    python -m scripts.build_index --backend gemma --split test     # test  -> cache/gemma_768_test.npz
    python -m scripts.build_index --backend gemma --force          # rebuild even if up to date
    python -m scripts.build_index --backend gemma --dim 256

The train index is what the router matches against. The test index is only for
scripts.evaluate, so test sentences are embedded once and evaluation runs offline.
"""

import argparse
import logging
import sys
import time

import numpy as np

from src.config import SPLITS, load_settings, with_overrides
from src.data import load_examples
from src.embeddings import BACKENDS, EmbeddingError, QuotaExceededError, make_embedder
from src.index import EmbeddingIndex, file_sha256
from src.logging_setup import setup_logging

log = logging.getLogger("build_index")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed an example set and cache the vectors.")
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--split", choices=SPLITS, default="train", help="which example set (default train)")
    parser.add_argument("--dim", type=int, help="vector size (default from config: 768)")
    parser.add_argument("--force", action="store_true", help="rebuild even if the index is up to date")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = with_overrides(load_settings(), dim=args.dim)

    source_path = settings.paths.examples(args.split)
    index_path = settings.paths.index_file(args.backend, settings.embedding.dim, args.split)
    source_hash = file_sha256(source_path)
    if not args.force and EmbeddingIndex.is_current(index_path, source_hash):
        log.info("%s is up to date (%s unchanged), skipping. Use --force to rebuild.", index_path.name, source_path.name)
        return 0

    examples = load_examples(source_path)
    log.info("%d %s examples from %s", len(examples), args.split, source_path.name)

    started = time.perf_counter()
    embedder = make_embedder(args.backend, settings)
    loaded = time.perf_counter()
    try:
        vectors = embedder.embed([ex.text for ex in examples])
    except QuotaExceededError as e:
        log.error("STOPPED: %s\nNothing was saved. Wait for the quota to reset, then run again.", e)
        return 2
    except EmbeddingError as e:
        log.error("CHECK FAILED: %s\nNothing was saved.", e)
        return 1
    finished = time.perf_counter()

    EmbeddingIndex(
        vectors=vectors,
        texts=np.array([ex.text for ex in examples]),
        intents=np.array([ex.intent for ex in examples]),
        langs=np.array([ex.lang for ex in examples]),
        model_id=embedder.model_id,
        dim=embedder.dim,
        prefix=embedder.prefix,
        source_sha256=source_hash,
    ).save(index_path)

    log.info("load %.1fs, embed %.1fs", loaded - started, finished - loaded)
    log.info("saved %s: vectors %s %s", index_path.name, vectors.shape, vectors.dtype)
    return 0


if __name__ == "__main__":
    sys.exit(main())
