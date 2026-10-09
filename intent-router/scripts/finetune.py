"""Fine-tune EmbeddingGemma on train.json (SetFit-style contrastive pairs) -> the "gemma-ft" backend.

    python -m scripts.finetune                  # LoRA (default)
    python -m scripts.finetune --full           # full fine-tuning (slower, more memory)
    python -m scripts.finetune --epochs 2 --rounds 8

20% of train.json (stratified by intent and language, seed 42) is held out as a
calibration split and never trained on. Writes models/gemma-ft/: the adapter (or full
model), calibration.json and metadata.json. Settings live in src/config.py (FinetuneConfig).

Then rebuild the gemma-ft indexes (--force after a re-run) and evaluate:
    python -m scripts.build_index --backend gemma-ft --force
    python -m scripts.build_index --backend gemma-ft --split test_synthetic --force
    python -m scripts.evaluate    --backend gemma-ft --test test_synthetic
"""

import argparse
import logging
import sys

from src.config import load_settings, with_overrides
from src.finetune import run_finetune
from src.logging_setup import setup_logging

log = logging.getLogger("finetune")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Contrastive fine-tuning of EmbeddingGemma on train.json.")
    parser.add_argument("--full", action="store_true", help="full fine-tuning instead of LoRA")
    parser.add_argument("--epochs", type=int, help="passes over the pairs (default from config: 1)")
    parser.add_argument("--batch-size", type=int, help="pairs per step (default from config: 16)")
    parser.add_argument("--rounds", type=int, help="pair rounds: 1 positive + 1 negative per sentence each (default 5)")
    parser.add_argument("--local-only", action="store_true", help="load the base model from the local cache only")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = with_overrides(
        load_settings(),
        gemma_local_only=args.local_only or None,
        finetune_full=args.full or None,
        finetune_epochs=args.epochs,
        finetune_batch_size=args.batch_size,
        finetune_pair_rounds=args.rounds,
    )
    metadata = run_finetune(settings.paths.train, settings.gemma, settings.embedding, settings.finetune)
    log.info(
        "done: %s, %d sentences trained on, %d held out for calibration",
        metadata.model_id, metadata.finetune_size, metadata.calibration_size,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
